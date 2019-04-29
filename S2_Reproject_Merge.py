import rasterio
from glob import glob
import rasterio.warp as warp
from rasterio.merge import merge
from rasterio.warp import Resampling
import rasterio.mask
import argparse
import os

parser = argparse.ArgumentParser(description=__doc__)
optional = parser._action_groups.pop()
required = parser.add_argument_group("required arguments")

required.add_argument("--ProcessingLevel", help="Specify S2 processing level, default=L1C", default="L1C")
required.add_argument("--SrcPath", help="Path to src product corresponding to the S2 products",
					  required=True)
required.add_argument("--S2Source", help="Path to S2 products source folder", required=True)
required.add_argument("--destination", help="Path to destination of reprojected and merged products",
					  required=True)

required.add_argument('--bands', '--names-list', nargs='+', default=['all'], 
					  help="Define bands you want to keep, default=all")
required.add_argument('--resampling', default="nearest",help="Resampling method to use from rasterio.warp.Resampling, default=nearest")


args = parser.parse_args()
S2path =args.S2Source
SITPath = args.SrcPath
dest = args.destination
bandsarg = args.bands
resampling_arg = args.resampling
processing_level = args.ProcessingLevel


all_bands_1C = ['B01', 'B02','B03','B04','B05','B06','B07','B08','B8A','B09','B10','B11', 'B12']
all_bands_2A = ['B01', 'B02','B03','B04','B05','B06','B07','B8A','B09','B11', 'B12']

if processing_level == "L1C":
	if bandsarg[0] == 'all':

		bands_name = all_bands_1C
	else:
		checkbands = [i for i in bandsarg if i in all_bands_1C]
		if len(checkbands)==0:
			raise ValueError("--bands must contain at least one of these elements: B01, B02, B03, B04', B05, B06, B07, B08, B8A, B09, B10, B11, B12")
		bands_name = bandsarg
elif processing_level == "L2A":
	if bandsarg[0] == 'all':

		bands_name = all_bands_2A
	else:
		checkbands = [i for i in bandsarg if i in all_bands_2A]
		if len(checkbands)==0:
			raise ValueError("--bands must contain at least one of these elements: B01, B02, B03, B04, B05, B06, B07, B8A, B09, B11, B12")
		bands_name = bandsarg
else:
	raise ValueError("--ProcessingLevel must either be L1C or L2A")

def resampling_method(method):
	if method == 'nearest':
		return Resampling.nearest
	elif method == 'bilinear':
		return Resampling.bilinear
	elif method == 'cubic':
		return Resampling.cubic
	elif method == 'cubic_spline':
		return Resampling.cubic_spline
	elif method == 'lanczos':
		return Resampling.lanczos
	elif method == 'average':
		return Resampling.average
	elif method == 'mode':
		return Resampling.mode
	elif method == 'max':
		return Resampling.max
	elif method == 'min':
		return Resampling.min
	elif method == 'med':
		return Resampling.med
	elif method == 'q1':
		return Resampling.q1
	elif method == 'q3':
		return Resampling.q3
	else:
		raise ValueError("Invalid method, does not exist, check rasterio.warp.Resampling for reference.")
		return None

def ReprojectS2Products(srcPath, S2Dir, destinationDir, procLevel):
	"""
		Function that reprojects and stacks each band of several S2 products to source raster. S2 products and source raster
		must overlap.

		srcPath: Path to source raster.
		S2Dir: Path to directory of S2 products in .SAFE format
		destinationDir: Path to destination directory where the resulting rasters will be stored


	"""
	# List of all S2 products paths
	if procLevel == "L1C":
		band_name_base = 4
		S2Products = glob(os.path.join(S2Dir, '*MSIL1C*'))
	else:
		band_name_base = 8
		S2Products = glob(os.path.join(S2Dir, '*MSIL2A*'))
	
	#print(S2Products)

	with rasterio.open(srcPath) as source:
		# Define profile for reprojection
		kwargs = source.profile
		for prod in S2Products:
			file_list = []
			file_listTOA = []
			
			prod_name = os.path.basename(prod)
			prod_name = prod_name[:len(prod_name) - 5]

			# Create temporary folder for storage
			destProd = os.path.join(destinationDir, prod_name)
			destProdToa = os.path.join(destProd, 'TOA')
			if not os.path.exists(destProd):
				os.makedirs(destProd)
			if not os.path.exists(destProdToa):
				os.makedirs(destProdToa)

			print("Reprojecting and stacking for S2 product: {}".format(prod_name))
			if procLevel == "L1C":
				imgPath = glob(os.path.join(prod, 'GRANULE', 'L*', 'IMG_DATA'))[0]
			else:
				imgPath = glob(os.path.join(prod, 'GRANULE', 'L*', 'IMG_DATA','R*'))[0]
			
			
			print("    Reprojecting Bands: ")
			for i, band_ in enumerate(bands_name):
			
				bfp = glob(os.path.join(imgPath, '*'+band_+'*'))[0]
				
				base = os.path.basename(bfp)
				
				base = base[:len(base) - band_name_base]
				
				print("        Band {}".format(base[-3:]))
				basetif = base + '.tif'
				
				TOAband = os.path.join(destProdToa, base+'_TOA.tif')
				file_listTOA.append(TOAband)
				destBand = os.path.join(destProd, basetif)
				
				file_list.append(destBand)

				with rasterio.open(bfp) as band:
					kwargsTOA = band.profile
					kwargsTOA.update({
							'dtype': 'float32',
							'driver':'Gtiff'
						}
					)
					
					bandTOA = band.read(1).astype('float32')/10000
					with rasterio.open(TOAband, 'w', **kwargsTOA) as dstTOA:
						dstTOA.write(bandTOA, 1)
						
				
				with rasterio.open(TOAband) as srcTOA:
					kwargs.update({'nodata': srcTOA.profile['nodata'],
									"driver": 'Gtiff',
									"dtype": "float32"})
					
					with rasterio.open(destBand, 'w', **kwargs) as dst:
						warp.reproject(
							rasterio.band(srcTOA, 1),
							rasterio.band(dst, 1),
							resampling=resampling_method(resampling_arg))

			# Stack the rasters, the delete the temporary files
			print("    Stacking bands...")

			stackDest = os.path.join(destinationDir, prod_name + '_stacked.tif')

			with rasterio.open(file_list[0]) as src0:
				kwargs = src0.profile
				kwargs.update(count=len(file_list))
			with rasterio.open(stackDest, 'w', **kwargs) as dst:
				for id, layer in enumerate(file_list, start=1):
					with rasterio.open(layer) as src1:
						dst.write_band(id, src1.read(1))
					os.remove(layer)
			for TOA in file_listTOA:
				os.remove(TOA)
			os.rmdir(destProdToa)
			os.rmdir(destProd)

			print("    Done!")
	print("All products in directory done processing!")


def MergeRasters(srcDir, dstDir, srcImgformat='tif', returnMerge=False):
	"""
		Merging rasters located in srcDir and written to 'merged.imgformat' in destDir
	"""
	if not os.path.exists(dstDir):
		os.makedirs(dstDir)
	if srcImgformat not in ('tif', 'jp2', 'TIF'):
		raise ValueError("Invalid image format, choose one of these instead: ('tif', 'jp2', 'TIF')")
	rasters = glob(os.path.join(srcDir, '*.{}'.format(srcImgformat)))
	destination = os.path.join(dstDir, 'merged.{}'.format(srcImgformat))
	datasets = []

	for img in rasters:
		datasets.append(rasterio.open(img))

	merged, output_transform = merge(datasets, nodata=0)

	with rasterio.open(rasters[0]) as src:
		kwargs = src.profile
	with rasterio.open(destination, 'w', **kwargs) as dst:
		dst.write(merged)

	for sets in datasets:
		sets.close()
	if returnMerge:
		return merged
	else:
		del merged
		return None

temporary_dir = os.path.join(dest, 'tmp')
ReprojectS2Products(SITPath, S2path, destinationDir=temporary_dir, procLevel=processing_level)

print("Merging rasters..")
MergeRasters(srcDir=temporary_dir, dstDir=dest, srcImgformat='tif', returnMerge=False)

files = glob(os.path.join(temporary_dir, '*'))
for file in files:
	os.remove(file)

os.rmdir(temporary_dir)

print("Done merging, final product will be found in destination: {}, with the name merged.tif".format(dest))

