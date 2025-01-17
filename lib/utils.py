import os
import traceback
import datetime
import pyproj
import requests
import numpy as np
from netCDF4 import Dataset

import boto3
from botocore import UNSIGNED
from botocore.config import Config

### function to log any errors that occur
def log_errors(error, output_dir, filename):
	with open(os.path.join(output_dir, filename),'a') as f:
		f.write('\n----------------------------------------\n')
		f.write(datetime.datetime.now().strftime("%m-%d-%Y") + '\n')
		f.write(str(error) + '\n')
		f.write(traceback.format_exc())

### function to find index of the closest value in an array
def find_idx_of_nearest_value(array, value):
	array = np.asarray(array)
	idx = (np.abs(array - value)).argmin()
	return idx

### function of check for existence of files for specific date
def check_file_exists(ftype, day, hour, destdir, lookback=None):
	'''Check if file exists in directory.
		ftype : options include LDASOUT,CHRTOUT,GWOUT
		day  : string date in format YYYYMMDD
		hour : hour to get file for as string HH
		destdir : directory to write data to
	'''
	if lookback == None:
		fname = f'NEUS_{day}{hour}00.{ftype}_DOMAIN1'
	else:
		fname = f'NEUS_{day}_nwm.t{hour}z.analysis_assim.{ftype}.tm{lookback}.conus.nc'

	savedFiles = os.listdir(destdir)
	return fname in savedFiles

### function to download NWM model output
def download_nwm(ftype, day, hour='12', lookback=None, destdir='./'):
	'''Download NWM file.
		ftype : options include LDASOUT, CHRTOUT (for retrospective data) or channel_rt, land (for operational data)
		day  : string date in format YYYYMMDD
		hour : hour to get file for as string HH
		lookback : typically '00'
		destdir : directory to write data to
	'''
	if lookback == None:
		yr = day[:4]
		fname = f'{day}{hour}00.{ftype}_DOMAIN1'
		s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
		s3.download_file(Bucket='noaa-nwm-retrospective-3-0-pds', Key=f'CONUS/netcdf/{ftype}/{yr}/{fname}', Filename=os.path.join(destdir, fname))
	else:
		fname = f'nwm.t{hour}z.analysis_assim.{ftype}.tm{lookback}.conus.nc'
		url = f'https://nomads.ncep.noaa.gov/pub/data/nccf/com/nwm/prod/nwm.{day}/analysis_assim/{fname}'
		r = requests.get(url)
		with open(os.path.join(destdir, fname), 'wb') as f:
			f.write(r.content)
	return fname

### function to remove NWM file
def remove_nwm(ftype, day=None, hour='12', lookback=None, locdir='./'):
	'''Remove NWM file.
		ftype : options include LDASOUT,CHRTOUT,GWOUT
		day  : string date in format YYYYMMDD
		hour : hour to get file for as string HH
		locdir : directory where file exists
	'''
	if lookback == None:
		fname = f'{day}{hour}00.{ftype}_DOMAIN1'
	else:
		fname = f'nwm.t{hour}z.analysis_assim.{ftype}.tm{lookback}.conus.nc'
	if os.path.exists(os.path.join(locdir, fname)): os.remove(os.path.join(locdir, fname))

def increment_date(curr_date):
  dt_date = datetime.datetime.strptime(curr_date,'%Y%m%d')
  dt_next = dt_date + datetime.timedelta(days=1)
  return dt_next.strftime('%Y%m%d')

def subset_soil_m_data(in_file, in_dir, out_file, out_dir, ll_lon, ll_lat, ur_lon, ur_lat):
	ncfile = Dataset(os.path.join(in_dir, in_file),'r')
	proj4_string = ncfile.getncattr('proj4')
	x = ncfile.variables['x'][:]
	y = ncfile.variables['y'][:]
	ncfile.close()

	### define a transformer
	p1 = pyproj.Proj(proj4_string)
	p2 = pyproj.Proj(proj='latlong', datum='WGS84')
	transformer = pyproj.Transformer.from_proj(p2, p1)

	### SW corner of NEUS grid
	fx,fy = transformer.transform(ll_lon,ll_lat)
	### Find indices of x,y arrays for SW corner of NEUS
	sw_x_idx = find_idx_of_nearest_value(x,fx)
	sw_y_idx = find_idx_of_nearest_value(y,fy)

	### NE corner of NEUS grid
	fx,fy = transformer.transform(ur_lon,ur_lat)
	### Find indices of x,y arrays for NE corner of NEUS
	ne_x_idx = find_idx_of_nearest_value(x,fx)
	ne_y_idx = find_idx_of_nearest_value(y,fy)

	### subset file (variables, NEUS region)
	subset_region = f'-d x,{str(sw_x_idx)},{str(ne_x_idx)} -d y,{str(sw_y_idx)},{str(ne_y_idx)}'
	crop_command = f'ncks {subset_region} -v SOIL_M {os.path.join(in_dir, in_file)} -O {os.path.join(out_dir, out_file)}'
	os.system(crop_command)