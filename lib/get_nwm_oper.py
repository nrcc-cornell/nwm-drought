'''
	Download NWM v3 operational model output for specified variables and date.

	Two files are retrieved:
		'channel' files (contains streamflow), and
		'land' files (contains soil moisture).
	The files for 12Z become available after 9:30 AM ET.

	orig bnb2, updated to python3 and NWM v3 be99
'''
import sys
import os
import datetime
import xarray as xr
import numpy as np

from .utils import download_nwm, remove_nwm, increment_date, check_file_exists, subset_soil_m_data
from .r2_bucket import R2Bucket

def get_nwm_oper(config, YYYYMMDD):
	# Get yesterday's date
	dt_yesterday = datetime.datetime.strptime(YYYYMMDD,'%Y%m%d') - datetime.timedelta(days=1)
	yesterdaydate = dt_yesterday.strftime('%Y%m%d')

	# Check if yesterday and today files already exist, use this to determine which days we need to fetch
	yesterdayExists = check_file_exists('channel_rt', yesterdaydate, config.hour, config.oper_data_dir, config.lookback) and check_file_exists('land', yesterdaydate, config.hour, config.oper_data_dir, config.lookback)
	todayExists = check_file_exists('channel_rt', YYYYMMDD, config.hour, config.oper_data_dir, config.lookback) and check_file_exists('land', YYYYMMDD, config.hour, config.oper_data_dir, config.lookback)
	if yesterdayExists and todayExists: return

	sdate = YYYYMMDD if yesterdayExists else yesterdaydate
	edate = yesterdaydate if todayExists else YYYYMMDD
	thisdate = sdate

	# Load streamflow ids for cropping CHANNEL data
	streamflow_ids = np.load(os.path.join(config.writable_dir, 'streamflow_ids.npy'))

	while thisdate <= edate:
		######################################
		### CHANNEL file does not contain auxiliary coordinates,
		###   so it is cropped using xarray and streamflow feature ids from a precalculated file.
		######################################
		ncfilename = download_nwm('channel_rt',thisdate,hour=config.hour,lookback=config.lookback,destdir=config.temp_dir)
		ncfilename_out = f'NEUS_{thisdate}_{ncfilename}'
		uncropped = xr.open_dataset(os.path.join(config.temp_dir, ncfilename), engine='netcdf4')
		cropped = uncropped.where(uncropped['feature_id'].isin(streamflow_ids), drop=True)[['streamflow']]
		cropped.to_netcdf(os.path.join(config.oper_data_dir, ncfilename_out))
		remove_nwm('channel_rt',hour=config.hour,lookback=config.lookback,locdir=config.temp_dir)

		######################################
		### SUBSET LAND FILE (retain SOIL_M for NEUS)
		### Subsetting this file requires transforming known lat/lon boundaries of region
		### of interest into the x/y coordinates specified by the projection. Once these
		### regional boundaries are known in x/y coordinates, grid indices of the regional
		### boundaries are obtained. We can then subset this dataset using ncks with the
		### following options:
		### 1) variables to retain: -v SOIL_M
		### 2) region of interest: -d x,sw_x_idx,ne_x_idx -d y,sw_y_idx,ne_y_idx
		######################################
		ncfilename = download_nwm('land',thisdate,hour=config.hour,lookback=config.lookback,destdir=config.temp_dir)
		ncfilename_out = f'NEUS_{thisdate}_{ncfilename}'
		subset_soil_m_data(ncfilename, config.temp_dir, ncfilename_out, config.oper_data_dir, config.ll_lon, config.ll_lat, config.ur_lon, config.ur_lat)
		remove_nwm('land',hour=config.hour,lookback=config.lookback,locdir=config.temp_dir)

		# Increment thisdate
		thisdate = increment_date(thisdate)

	# Make sure both files now exist
	yesterdayExists = check_file_exists('channel_rt', yesterdaydate, config.hour, config.oper_data_dir, config.lookback) and check_file_exists('land', yesterdaydate, config.hour, config.oper_data_dir, config.lookback)
	todayExists = check_file_exists('channel_rt', YYYYMMDD, config.hour, config.oper_data_dir, config.lookback) and check_file_exists('land', YYYYMMDD, config.hour, config.oper_data_dir, config.lookback)
	dts = None
	if not yesterdaydate and not todayExists:
		dts = f'{YYYYMMDD} and {yesterdaydate}'
	elif not yesterdayExists:
		dts = yesterdaydate
	elif not todayExists:
		dts = YYYYMMDD

	if dts: sys.exit(f'ERROR: files for {dts} were not downloaded')

	# Get list of files currently in R2 bucket
	r2 = R2Bucket(
		os.environ['R2_BUCKET_NAME'],
		os.environ['CF_ACCOUNT_ID'],
		os.environ['R2_ACCESS_KEY_ID'],
		os.environ['R2_SECRET_ACCESS_KEY']
	)
	bucket_files = [obj.key for obj in r2.bucket.objects.all()]

	# Construct list of dates to keep locally. Each date in list is of the format YYYYMMDD.
	start_YYYYMMDD = (datetime.datetime.strptime(YYYYMMDD,'%Y%m%d') + datetime.timedelta(days=2)).strftime('%Y%m%d')
	dates_to_keep = [
		(datetime.datetime.strptime(start_YYYYMMDD,'%Y%m%d') - datetime.timedelta(days=idy)).strftime('%Y%m%d')
		for idy in range(config.numdays_in_period)
	]

	# Dates that are not in the range of interest are moved to R2 bucket in case they are needed later.
	local_files = os.listdir(config.oper_data_dir)
	for f in local_files:
		file_YYYYMMDD = f[5:13]
		f_path = os.path.join(config.oper_data_dir,f)

		if f not in bucket_files:
			r2.bucket.upload_file(f_path, f)
		if file_YYYYMMDD not in dates_to_keep and os.path.exists(f_path):
			os.remove(f_path)