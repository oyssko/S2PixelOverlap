# S2PixelOverlap
Scripts for finding Sentinel-2 products from valid pixels and reprojecting and merging sentinel-2 rasters

## Installation

It's recommended to create a virtual environment using anaconda or miniconda first by:

```
>conda create -n venv python=3.6
```

Will create a virtual environment called venv with python version 3.6, activate by:
```
>conda activate venv
```

For installing the required packaged for running the scripts, first install the Rasterio package with the [guide](https://rasterio.readthedocs.io/en/stable/installation.html) from Rasterio
documentation.

Next, install the packages in the 'requirements.txt' file:
```
pip install -r requirements.txt
```

## Running the scripts:
### `Mask_S2_Overlap.py`
`Mask_S2_Overlap.py` searches for overlapping Sentinel-2 Level 1C products for a given mask with some defined valid pixel values.

Run using the ipython interface:
```
>ipython
Python 3.6.7 (default, Feb 28 2019, 07:28:18) [MSC v.1900 64 bit (AMD64)]
Type 'copyright', 'credits' or 'license' for more information
IPython 7.4.0 -- An enhanced Interactive Python. Type '?' for help.

In [1]: run Mask_S2_Overlap.py --MaskPath "PATH TO MASK RASTER" --ValidInterval min max --credentials "userpass.txt"
```
Usage is shown below:
```
usage: Mask_S2_Overlap.py [-h] --MaskPath MASKPATH
                          [--ValidInterval VALIDINTERVAL [VALIDINTERVAL ...]]
                          [--ValidValues VALIDVALUES [VALIDVALUES ...]]
                          [--cloudcover CLOUDCOVER] [--delta DELTA]
                          --credentials CREDENTIALS
                          [--minS2pixels MINS2PIXELS]
                          [--minS2pixelPerc MINS2PIXELPERC]

Module created for script run in IPython

required arguments:
  --MaskPath MASKPATH   Path to mask product
  --ValidInterval VALIDINTERVAL [VALIDINTERVAL ...]
                        Interval of values from mask
  --ValidValues VALIDVALUES [VALIDVALUES ...], --list VALIDVALUES [VALIDVALUES ...]
                        Valid values for mask
  --cloudcover CLOUDCOVER
                        Cloud cover percentage (min, max)
  --delta DELTA         Time difference from SIT product
  --credentials CREDENTIALS
                        Path to .txt file specifying username and password for
                        copernicus.com
  --minS2pixels MINS2PIXELS
                        Minimum amount of valid pixels in S2
                        product,default=2000
  --minS2pixelPerc MINS2PIXELPERC
                        Minimum percentage of valid pixels in S2 product,
                        default=20
```

The script returns a list called `kept_products` that include all the metadata information for each valid 
overlapping Sentinel 2 product. Downloading the products is easy, after running the script, simply run this code next:
```Python
   ...:for prod in kept_products:
   ...:
   ...:
   ...:     Sentinel2api.download(prod['uuid'], directory_path=destination)

```
Where destination is the path to where you want your products downloaded. The S2 products are downloaded in 
.SAFE format.
### `S2_Reproject_Merge.py`
When the valid Sentinel-2 products are downloaded, the second script will reproject and merge the sentinel 2 products such that each pixel correspond to the valid pixels from the previous mask raster, in this case the source raster in `SrcPath`. Example usage:

```
In [2]: run S2_Reproject_Merge.py --ProcessingLevel L1C --S2Source "PATH TO FOLDER WITH S2 PRODUCTS" --SrcPath "PATH TO SOURCE RASTER" 
...:--destination "PATH TO FOLDER WHERE FINAL PRODUCT IS STORED AS merged.tif" --bands all --resampling nearest
```
If you have applied atmospheric correction using ESA's [Sen2Cor](http://step.esa.int/main/third-party-plugins-2/sen2cor/) processor, you can also
reproject and merge the Level 2A products by specifying `--ProcessingLevel` as `L2A`.
Usage is defined here:.
```
usage: S2_Reproject_Merge.py [-h] [--ProcessingLevel PROCESSINGLEVEL]
                             --SrcPath SRCPATH --S2Source S2SOURCE
                             --destination DESTINATION
                             [--bands BANDS [BANDS ...]]
                             [--resampling RESAMPLING]

Module created for script run in IPython

required arguments:
  --ProcessingLevel PROCESSINGLEVEL
                        Specify S2 processing level, default=L1C
  --SrcPath SRCPATH     Path to src product corresponding to the S2 products
  --S2Source S2SOURCE   Path to S2 products source folder
  --destination DESTINATION
                        Path to destination of reprojected and merged products
  --bands BANDS [BANDS ...], --names-list BANDS [BANDS ...]
                        Define bands you want to keep, default=all
  --resampling RESAMPLING
                        Resampling method to use from
                        rasterio.warp.Resampling, default=nearest
```

## ACOLITE Processor

There are two scripts, `Acolite_AC_process.py` and `Reproject_acolite.py`, the first script applies the atmospheric
correction to a set of Sentinel-2 products in .SAFE format, merging them and resamples them to either 10m, 20m or 60m
resolution, the second script takes the result from the ACOlITE AC process and reprojects the rasters to a different
coordinate reference system given by another raster. Similar to `S2_Reproject_Merge.py`, but without merging and works only
for output from ACOLITE The scripts are still work in progress.

You need the ACOLITE AC processor to run the script. It's available for download from the [Royal Belgian Institute of Natural Sciences](https://odnature.naturalsciences.be/remsem/software-and-data/acolite).
Download "ACOLITE for windows", unzip the file and add the 'acolite_py_win' folder in the same directory as the ACOLITE scripts. `acolite_settings.txt` is
a configuration file for the ACOLITE AC process and is generated from the input parameters in the `Acolite_AC_process.py` script.
 







