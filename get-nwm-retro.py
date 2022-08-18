'''Download NWM retrospective output.

	Download NWM v2.1 retrospective model (1979-2020) for specified variable and dates.
	A rolling window of data is maintained, specified by YYYYMMDD and numdays_in_period.

	user settings:
		YYYYMMDD : str : date of interest (defaults to today's date if not provided)
		numdays_in_period : int : number of days to to retrieve.
			NOTE this will include two days after YYYYMMDD and 
			remainder of days before YYYYMMDD.
			Example: If YYYYMMDD='20220815' and numdays_in_period=7, then
			the following dates are retrived for each year:
			['0811','0812','0813','0814','0815','0816','0817']
		ll_lon,ll_lat,ur_lon,ur_lat : float : lower-left, upper-right corners
			of region of interest. Used to crop LDASOUT only.
		vars_chrtout : list : variable names to extract from CHRTOUT files.
		vars_ldasout : list : variable names to extrat from LDASOUT files.
		tmpdir : str : path to directory used as a workspace
		outdir : str : path where downloaded/cropped/filtered files are saved.

	usage:
		python get-nwm-retro.py <YYYYMMDD>

	bnb2
'''
import os,sys
import datetime
import numpy as np
from netCDF4 import Dataset
import pyproj

######################################
### User settings for subsetting datasets
######################################
### NEUS region of interest. Dataset will be cropped to this region.
ll_lon = -83.00
ll_lat = 37.15
ur_lon = -65.00
ur_lat = 47.00
### variables from CHRTOUT. Dataset will only contain these variables (plus dimensions).
#vars_chrtout=['streamflow','qBtmVertRunoff']
vars_chrtout=['streamflow']
### variables from LDASOUT. Dataset will only contain these variables (plus dimensions).
#vars_ldasout=['SOIL_M','ACCET']
vars_ldasout=['SOIL_M']
### location to store subset NWM files
#outdir = '/home/bnb2/nedews-nwm/nwm_subset_ne_historical/'
outdir = 'nwm_retro_data/'
### lcoation to store full downloaded NWM files temporarily
#tmpdir = '/home/bnb2/nedews-nwm/workspace/'
tmpdir = 'workspace/'
### number of days in period of interest to retrieve retro output each year.
# Our longest lookback for products is 28 days. Add a few days as cushion in
# case data source is temporarily unavailable. Data are rotated off as to only
# maintain a data window of this size, relative to current date.
#numdays_in_period = 33
numdays_in_period = 4

######################################
### Functions
######################################
### function to find index of the closest value in an array
def findIdxOfNearestValue(array, value):
	array = np.asarray(array)
	idx = (np.abs(array - value)).argmin()
	return idx

### function to download NWM model output
def checkFileExists(ftype,day,hour='12',destdir='./'):
	'''Check if file exists in directory.
		ftype : options include LDASOUT,CHRTOUT,GWOUT
		day  : string date in format YYYYMMDD
		hour : hour to get file for as string HH
		destdir : directory to write data to
	'''
	yr = day[:4]
	fname = 'NEUS_'+day+hour+'00.'+ftype+'_DOMAIN1.comp'
	savedFiles = os.listdir(destdir)
	return fname in savedFiles

### function to download NWM model output
def downloadNWM(ftype,day,hour='12',destdir='./'):
	'''Download NWM file.
		ftype : options include LDASOUT,CHRTOUT,GWOUT
		day  : string date in format YYYYMMDD
		hour : hour to get file for as string HH
		destdir : directory to write data to
	'''
	yr = day[:4]
	fname = day+hour+'00.'+ftype+'_DOMAIN1.comp'
	cmd = 'aws s3 cp s3://noaa-nwm-retrospective-2-1-pds/model_output/'+yr+'/'+fname+' '+destdir+' --no-sign-request --only-show-errors'
	res = os.system(cmd)
	return fname

### function to remove NWM file
def removeNWM(ftype,day,hour='12',locdir='./'):
	'''Remove NWM file.
		ftype : options include LDASOUT,CHRTOUT,GWOUT
		day  : string date in format YYYYMMDD
		hour : hour to get file for as string HH
		locdir : directory where file exists
	'''
	fname = day+hour+'00.'+ftype+'_DOMAIN1.comp'
	if os.path.exists(locdir+fname): res = os.remove(locdir+fname)
	return

######################################
### MAIN
######################################
### Create temporary and destination directories if they do not exist.
outdir = outdir if outdir[-1]=='/' else outdir+'/'
outputDirExists = os.path.exists(outdir)
if not outputDirExists: res = os.system('mkdir -p '+outdir)
tmpdir = tmpdir if tmpdir[-1]=='/' else tmpdir+'/'
tmpDirExists = os.path.exists(tmpdir)
if not tmpDirExists: res = os.system('mkdir -p '+tmpdir)

### Assign date of interest (YYYYMMDD, defaults to current day).
if len(sys.argv)==1:
	# current day
	YYYYMMDD = datetime.datetime.today().strftime('%Y%m%d')
else:
	# provided day from command line argument
	YYYYMMDD = sys.argv[1] if (type(sys.argv[1]) is str) else str(sys.argv[1])

### First year of retro output does not include beginning of year.
### Analyses for dates before Mar 15 will only include output for 1979.
if YYYYMMDD[-4:]>='0315':
	sdate = '19790101'
else:
	sdate = '19800101'
# As of 2022, NWM restrospective output only available through 2020
edate = '20201231'

### Construct list of dates to get. Each date in list is of the format MMDD.
### Using a leap year to ensure Feb 29 is in the list of dates, if necessary.
### This list of dates is used to retrieve a range of dates for each historical year.
start_YYYYMMDD = (datetime.datetime.strptime('2016'+YYYYMMDD[-4:],'%Y%m%d') + datetime.timedelta(days=2)).strftime('%Y%m%d')
dates_to_get = [
	(datetime.datetime.strptime(start_YYYYMMDD,'%Y%m%d') - datetime.timedelta(days=idy)).strftime('%m%d')
	for idy in range(numdays_in_period)
	]

### Remove files from output directory that are not in the date range of interest.
### These files are large, and rotating the saved files will save space.
savedFiles = os.listdir(outdir)
for f in savedFiles:
	MMDD = f[9:13]
	if MMDD not in dates_to_get and os.path.exists(outdir+f): res = os.remove(outdir+f)

### loop through days between start and end dates
thisdate = sdate
while thisdate <= edate:

	# Check if we should be downloading this date. If not, continue to next date.
	# 1) skip date if it is not in dates_to_get
	# 2) skip date if the file already exists in the output directory (previously downloaded)
	validDate = thisdate[-4:] in dates_to_get
	CHRTOUT_fileExists = checkFileExists('CHRTOUT',thisdate,hour='12',destdir=outdir)
	LDASOUT_fileExists = checkFileExists('LDASOUT',thisdate,hour='12',destdir=outdir)
	fileExists = CHRTOUT_fileExists and LDASOUT_fileExists
	if not validDate or fileExists:
		# only update thisdate for this iteration, then continue without retrieving files
		dt_date = datetime.datetime.strptime(thisdate,'%Y%m%d')
		dt_next = dt_date + datetime.timedelta(days=1)
		thisdate = dt_next.strftime('%Y%m%d')
		continue

	######################################
	### SUBSET CHRTOUT FILE (retain streamflow,qBtmVertRunoff for NEUS)
	### The file for CHRTOUT_DOMAIN1 contain auxiliary coordinates. We can subset this type
	### of file by using ncks with the following options:
	### 1) the variables to retain: -v streamflow,qBtmVertRunoff
	### 2) the extreme lat/lon for region of interest: -X ll_lon,ur_lon,ll_lat,ur_lat
	######################################
	ncfilename = downloadNWM('CHRTOUT',thisdate,hour='12',destdir=tmpdir)
	ncfilename_out = 'NEUS_'+ncfilename
	subset_region = "-X "+str(ll_lon)+","+str(ur_lon)+","+str(ll_lat)+","+str(ur_lat)
	subset_vars = "-v "+",".join(vars_chrtout)
	#crop_command = "ncks "+subset_region+" "+subset_vars+" "+tmpdir+ncfilename+" -O "+outdir+ncfilename_out
	crop_command = "ncks "+subset_vars+" "+tmpdir+ncfilename+" -O "+outdir+ncfilename_out
	res = os.system(crop_command)
	removeNWM('CHRTOUT',thisdate,hour='12',locdir=tmpdir)

	######################################
	### SUBSET LDASOUT FILE (retain SOIL_M,ACCET for NEUS)
	### Subsetting this file requires transforming known lat/lon boundaries of region
	### of interest into the x/y coordinates specified by the projection. Once these
	### regional boundaries are known in x/y coordinates, grid indices of the regional
	### boundaries are obtained. We can then subset this dataset using ncks with the
	### following options:
	### 1) variables to retain: -v SOIL_M,ACCET
	### 2) region of interest: -d x,sw_x_idx,ne_x_idx -d y,sw_y_idx,ne_y_idx
	######################################
	ncfilename = downloadNWM('LDASOUT',thisdate,hour='12',destdir=tmpdir)
	ncfilename_out = 'NEUS_'+ncfilename
	ncfile = Dataset(tmpdir+ncfilename,'r')
	proj4_string = ncfile.getncattr('proj4')
	x = ncfile.variables['x'][:]
	y = ncfile.variables['y'][:]
	ncfile.close()

	p1 = pyproj.Proj(proj4_string)
	p2 = pyproj.Proj(proj='latlong', datum='WGS84')

	### SW corner of NEUS grid
	fx,fy = pyproj.transform(p2,p1,ll_lon,ll_lat)
	### Find indices of x,y arrays for SW corner of NEUS
	sw_x_idx = findIdxOfNearestValue(x,fx)
	sw_y_idx = findIdxOfNearestValue(y,fy)

	### NE corner of NEUS grid
	fx,fy = pyproj.transform(p2,p1,ur_lon,ur_lat)
	### Find indices of x,y arrays for NE corner of NEUS
	ne_x_idx = findIdxOfNearestValue(x,fx)
	ne_y_idx = findIdxOfNearestValue(y,fy)

	### subset file (variables, NEUS region)
	subset_region = "-d x,"+str(sw_x_idx)+","+str(ne_x_idx)+" -d y,"+str(sw_y_idx)+","+str(ne_y_idx)
	subset_vars = "-v "+",".join(vars_ldasout)
	crop_command = "ncks "+subset_region+" "+subset_vars+" "+tmpdir+ncfilename+" -O "+outdir+ncfilename_out
	res = os.system(crop_command)
	removeNWM('LDASOUT',thisdate,hour='12',locdir=tmpdir)

	######################################
	# update thisdate
	dt_date = datetime.datetime.strptime(thisdate,'%Y%m%d')
	dt_next = dt_date + datetime.timedelta(days=1)
	thisdate = dt_next.strftime('%Y%m%d')

