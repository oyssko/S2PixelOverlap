import rasterio
import fiona
import rasterio.warp as warp
from rasterio.mask import mask
import os
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import mapping, shape
from affine import Affine
from pyproj import Proj, transform


def createFootprint(pathname):
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
    
    # Take only the edge pixels of the raster
	right = lonlat[:, 0, :][0::100]  # right
	down = lonlat[-1, :, :][0::100]  # down
	left = np.flip(lonlat[:, -1, :][0::100], axis=0)  # left
	up = np.flip(lonlat[0, :, :][0::100], axis=0)  # up
	up[-1] = right[0]
	footprint_arr = np.concatenate((right, down, left, up), axis=0).tolist()
    # Create geojson like file
	geom = {
            "type": "Polygon",
            "coordinates": [
                
                ]
            }
    # Append the footprint coordinates to the json
	geom["coordinates"].append(footprint_arr)

	return geom

def apply_landmask(rasterfp, detail=True, keep_land=False, mask_only=False):
	"""
	Function for applying landmask, using a landmask shapefile in the included folder

	rasterfp - path to raster
	detail - Get detailed high resolution land mask if True (slow, high memory), else using a more rough, but much faster
	and efficient
	keep_land - Mask out land (False), or keep only the land pixels (True)
	crop - crop out the masked out area (True) or return just the mask (False)
	"""
	# create Footprint for raster
	footprint = createFootprint(rasterfp)

	if detail:
		landpoly = r"include/land_polygons.shp"
	else:
		landpoly = r"include/GSHHS_i_L1.shp"

	with fiona.open(landpoly) as shapefile:
		# Use shapely for finding intersections between raster and land shapefile
		# by checking the shape intersects with the created footprint
		# Saves memory by not loading the whole shape, though it takes some time
		intersections = [mapping(shape(feature['geometry'])) for feature in shapefile 
						 if shape(feature['geometry']).intersects(shape(footprint))]
		# Get shapefiles crs
		crsShape = shapefile.crs

	# Check if there are any intersections, if there are none, just return a message.
	if len(intersections) == 0:
		print("There are no lands within the raster. Returning None")
		return None

	# If there are, apply the mask:
	else:
		# Use rasterio.warp's transform_geom to transform the intersection shapes crs to the rasters crs
		# then mask out the pixels that's within the shapes using rasterio.mask's mask method
		with rasterio.open(rasterfp) as src:
			kwargs = src.profile
			intersect_trans =  [warp.transform_geom(crsShape, src.crs, land) for land in intersections]
			landmasked_raster, transform = mask(src, intersect_trans, invert=~keep_land)
		
		if mask_only:
			mask_only_raster = np.zeros_like(landmasked_raster)
			mask_only_raster[0] = (landmasked_raster[0] == 0).astype('uint16')
			return mask_only_raster, kwargs
		else:
			return landmasked_raster, kwargs
	