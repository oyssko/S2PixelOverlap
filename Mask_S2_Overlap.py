from collections import defaultdict
import argparse
import rasterio
from glob import glob
import os
import rasterio.warp as warp
import rasterio.mask
from affine import Affine
from pyproj import Proj, transform
import shapely.wkt
from shapely.geometry import mapping
import dateparser
import numpy as np
from geojson import dump
from sentinelsat import SentinelAPI, geojson_to_wkt
from datetime import timedelta

parser = argparse.ArgumentParser(description=__doc__)
optional = parser._action_groups.pop()
required = parser.add_argument_group("required arguments")

required.add_argument("--MaskPath", help="Path to mask product", required=True)
required.add_argument("--ValidInterval", nargs="+",type=int, default=[0,0], help="Interval of values from mask")
required.add_argument("--ValidValues",'--list', nargs='*',type=int,default=[], help='Valid values for mask')
required.add_argument("--cloudcover",default=(0,30), help="Cloud cover percentage (min, max)")
required.add_argument("--delta", default="hours=1", help="Time difference from SIT product")
required.add_argument("--credentials", help="Path to .txt file specifying username and password for copernicus.com",
					  required=True)
required.add_argument("--minS2pixels", default=2000, type=int, 
					  help="Minimum amount of valid pixels in S2 product,default=2000")
required.add_argument("--minS2pixelPerc", default=20, type=int, 
					  help="Minimum percentage of valid pixels in S2 product, default=20")
					  
args = parser.parse_args()
cloudcover = args.cloudcover
path = args.MaskPath
txtpath = args.credentials
delta = args.delta
validvals = args.ValidValues
validinterval = args.ValidInterval
minS2pixels=args.minS2pixels
minS2pixelPerc = args.minS2pixelPerc


if (len(validvals) == 0) and (sum(validinterval)==0):
	raise ValueError("Need input for either --ValidInterval or --ValidValues")
	

def createFootprint(pathname, saveasGeojson=True, name=None):
	# Read raster
	with rasterio.open(pathname) as r:
		T0 = r.transform  # upper-left pixel corner affine transform
		p1 = Proj(r.crs)
		A = r.read(1)  # pixel values

	# All rows and columns
	cols, rows = np.meshgrid(np.arange(A.shape[1]), np.arange(A.shape[0]))

	# Get affine transform for pixel centres
	T1 = T0 * Affine.translation(0.5, 0.5)
	# Function to convert pixel row/column index (from 0) to easting/northing at centre
	rc2en = lambda r, c: (c, r) * T1

	# All eastings and northings (there is probably a faster way to do this)
	eastings, northings = np.vectorize(rc2en, otypes=[np.float, np.float])(rows, cols)

	# Project all longitudes, latitudes
	p2 = Proj(proj='latlong', datum='WGS84')
	longs, lats = transform(p1, p2, eastings, northings)

	lonlat = np.zeros((longs.shape + (2,)))

	lonlat[..., 0] = longs
	lonlat[..., 1] = lats

	def write_json(geom_in_geojson, name):
		# feature is a shapely geometry type
		fp = name + '.geojson'
		with open(fp, 'w') as outfile:
			dump(geom_in_geojson, outfile)

	right = lonlat[:, 0, :][0::100]  # right
	down = lonlat[-1, :, :][0::100]  # down
	left = np.flip(lonlat[:, -1, :][0::100], axis=0)  # left
	up = np.flip(lonlat[0, :, :][0::100], axis=0)  # up
	up[-1] = right[0]

	footprint_arr = np.concatenate((right, down, left, up), axis=0).tolist()
	geom = {
		"type": "FeatureCollection",
		"features": [
			{
				"type": "Feature",
				"properties": {},
				"geometry": {
					"type": "Polygon",
					"coordinates": [

					]
				}
			}
		]
	}
	geom["features"][0]["geometry"]["coordinates"].append(footprint_arr)

	if saveasGeojson:
		write_json(geom, name)

	return lonlat, geom


def deltaTimeSIT(path, delta="hours=1"):
	# Derive time from pathname
	time = os.path.basename(path)[:22]

	# Parse time for dateparser method
	year = time[0:4]
	month = time[4:6]
	day = time[6:8]
	hour = time[9:11]
	minute = time[11:13]

	parseTime = dateparser.parse(day + '-' + month + '-' + year + ' ' + hour + ':' + minute,
								 settings={"DATE_ORDER": "DMY"})

	# Calculate time differenct
	td_split = delta.split("=")
	if td_split[0] == "minutes":
		td = timedelta(minutes=int(td_split[1]))
	elif td_split[0] == "hours":
		td = timedelta(hours=int(td_split[1]))
	elif td_split[0] == "days":
		td = timedelta(days=int(td_split[1]))

	# Define interval of time for searching
	starttime = parseTime - td
	endtime = parseTime + td

	return starttime, endtime


def createSITMask(path, name='SIT_pixels'):
	print("Creating temperorary SIT mask raster...")
	# Creating the SIT mask and writing it as raster
	with rasterio.open(path) as r:
		kwds = r.profile

		data = r.read(1)
		
		if len(validvals) == 0:
			SIT_pixels = ((data >= validinterval[0]) & (data <= validinterval[1])).astype(np.uint8) * 100
		else:
			SIT_pixels = np.isin(data, validvals)*100

		with rasterio.open(name + '.tif', 'w', **kwds) as d:
			d.write(SIT_pixels, 1)
	print('Creating raster, done.')


def searchSITPixels(pathSIT, S2Odict, minSIT_pixels=2000, minSIT_percent=20):
	kept_products = []

	# Using the raster mask to map the S2 footprints and calculate the amount of SIT pixels
	# In each S2 product
	with rasterio.open(pathSIT) as r:

		for prod in S2Odict.values():
			footShape = shapely.wkt.loads(prod['footprint'])
			foot = mapping(footShape)
			geom_S2_trans = warp.transform_geom({'init': 'epsg:4326'}, r.crs, foot)

			masked, out_trans = rasterio.mask.mask(r, [geom_S2_trans])

			SIT_pix = masked[0] == 100
			NO_SIT = masked[0] == 0

			perc_sit = (np.sum(SIT_pix) / (np.sum(NO_SIT) + np.sum(SIT_pix))) * 100
			print('Product ID: ', prod['identifier'])
			print("Percentage of thin sea ice pixels are: {}%".format(np.round(perc_sit, 2)))
			print("With {} valid pixels".format(np.sum(SIT_pix)))
			if (perc_sit >= minSIT_percent) & (np.sum(SIT_pix) >= minSIT_pixels):
				kept_products.append(prod)

	return kept_products


def parseUserPass(txtPath):
	with open(txtPath, 'r') as fopen:
		userpass = fopen.read()
		username, password = userpass.split(', ')
	return (username, password)

print("Creating Footprint...")
lonlat, geom = createFootprint(path, saveasGeojson=False)
print("Footprint created for {}".format(os.path.basename(path)))
starttime, endtime = deltaTimeSIT(path, delta)

#Username and password from https://scihub.copernicus.eu/dhus

user, password = parseUserPass(txtpath)

Sentinel2api = SentinelAPI(user, password)

print("Searching for Sentinel-2 level 1 products within specified time...")
S2products1C = Sentinel2api.query(geojson_to_wkt(geom),
							  date = (starttime,endtime),
							  platformname = 'Sentinel-2',
							  cloudcoverpercentage = cloudcover,
							  producttype="S2MSI1C")

name = 'SIT_pixels'
createSITMask(path, name=name)

kept_products = searchSITPixels(name + '.tif', S2products1C, minSIT_pixels=minS2pixels, 
								minSIT_percent=minS2pixelPerc)
os.remove(name+'.tif')

