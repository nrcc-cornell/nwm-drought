'''
	Download NWM retrospective output.

	Download NWM v3 retrospective model (1979-2020) for specified variable and dates.
	A rolling window of data is maintained, specified by YYYYMMDD and numdays_in_period.

	orig bnb2, updated to python3 and NWM v3 be99
'''
import os
import datetime

from .utils import download_nwm, remove_nwm, increment_date, check_file_exists, subset_soil_m_data

def get_nwm_retro(config, YYYYMMDD, syear):
	# First year of retro output does not include beginning of year.
	sdate = f'{syear}0101'
	# As of 2022, NWM restrospective output only available through 2020
	edate = '20201231'

	# Construct list of dates to get. Each date in list is of the format MMDD.
	# Using a leap year to ensure Feb 29 is in the list of dates, if necessary.
	# This list of dates is used to retrieve a range of dates for each historical year.
	start_YYYYMMDD = (datetime.datetime.strptime('2016'+YYYYMMDD[-4:],'%Y%m%d') + datetime.timedelta(days=2)).strftime('%Y%m%d')
	dates_to_get = [
		(datetime.datetime.strptime(start_YYYYMMDD,'%Y%m%d') - datetime.timedelta(days=idy)).strftime('%m%d')
		for idy in range(config.numdays_in_period)
	]

	# Remove files from output directory that are not in the date range of interest.
	# These files are large, and rotating the saved files will save space.
	savedFiles = os.listdir(config.retro_data_dir)
	for f in savedFiles:
		MMDD = f[9:13]
		f_path = os.path.join(config.retro_data_dir,f)
		if MMDD not in dates_to_get and os.path.exists(f_path): os.remove(f_path)

	# Loop through days between start and end dates
	thisdate = sdate
	while thisdate <= edate:
		# Check if we should be downloading this date. If not, continue to next date.
		# 1) skip date if it is not in dates_to_get
		# 2) skip date if the file already exists in the output directory (previously downloaded)
		# # NOTE: these checks are done separately because checking date first is much faster
		validDate = thisdate[-4:] in dates_to_get
		if not validDate: 
			thisdate = increment_date(thisdate)
			continue
		CHRTOUT_fileExists = check_file_exists('CHRTOUT',thisdate,hour=config.hour,destdir=config.retro_data_dir)
		LDASOUT_fileExists = check_file_exists('LDASOUT',thisdate,hour=config.hour,destdir=config.retro_data_dir)
		fileExists = CHRTOUT_fileExists and LDASOUT_fileExists
		if fileExists:
			thisdate = increment_date(thisdate)
			continue

		######################################
		### SUBSET CHRTOUT FILE (retain streamflow variable for NEUS)
		### The file for CHRTOUT_DOMAIN1 contain auxiliary coordinates. We can subset this type
		### of file by using ncks with the following options:
		### 1) the variables to retain: -v streamflow
		### 2) the extreme lat/lon for region of interest: -X ll_lon,ur_lon,ll_lat,ur_lat
		######################################
		ncfilename = download_nwm('CHRTOUT',thisdate,hour=config.hour,destdir=config.temp_dir)
		ncfilename_out = f'NEUS_{ncfilename}'
		subset_region = f'-X {str(config.ll_lon)},{str(config.ur_lon)},{str(config.ll_lat)},{str(config.ur_lat)}'
		crop_command = f'ncks {subset_region} -v streamflow {os.path.join(config.temp_dir, ncfilename)} -O {os.path.join(config.retro_data_dir, ncfilename_out)}'
		os.system(crop_command)
		remove_nwm('CHRTOUT',day=thisdate,hour=config.hour,locdir=config.temp_dir)

		######################################
		### SUBSET LDASOUT FILE (retain SOIL_M variable for NEUS)
		### Subsetting this file requires transforming known lat/lon boundaries of region
		### of interest into the x/y coordinates specified by the projection. Once these
		### regional boundaries are known in x/y coordinates, grid indices of the regional
		### boundaries are obtained. We can then subset this dataset using ncks with the
		### following options:
		### 1) variables to retain: -v SOIL_M
		### 2) region of interest: -d x,sw_x_idx,ne_x_idx -d y,sw_y_idx,ne_y_idx
		######################################
		ncfilename = download_nwm('LDASOUT',thisdate,hour=config.hour,destdir=config.temp_dir)
		ncfilename_out = f'NEUS_{ncfilename}'
		subset_soil_m_data(ncfilename, config.temp_dir, ncfilename_out, config.retro_data_dir, config.ll_lon, config.ll_lat, config.ur_lon, config.ur_lat)
		remove_nwm('LDASOUT',day=thisdate,hour=config.hour,locdir=config.temp_dir)

		# Increment thisdate
		thisdate = increment_date(thisdate)