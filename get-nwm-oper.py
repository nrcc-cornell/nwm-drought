'''Download operational NWM files.

	Download NWM v2.1 operational model output for specified variables and date.
	Two files are retrieved:
		'channel' files (contains streamflow), and
		'land' files (contains soil moisture).
	The files for 12Z become available after 9:30 AM ET.

	user settings:
		YYYYMMDD : str : date of interest (defaults to today's date if not provided)
		ll_lon,ll_lat,ur_lon,ur_lat : float : lower-left, upper-right corners
			of region of interest. Used to crop 'land' file only.
		vars_channel : list : variable names to extract from 'channel' files.
		vars_land : list : variable names to extrat from 'land' files.
		tmpdir : str : path to directory used as a workspace
		outdir : str : path where downloaded/cropped/filtered files are saved.

	usage:
		python get-nwm-oper.py <YYYYMMDD>

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
### variables from CHANNEL_RT. Dataset will only contain these variables (plus dimensions).
vars_channel=['streamflow']
### variables from LAND. Dataset will only contain these variables (plus dimensions).
vars_land=['SOIL_M']
### location to store subset NWM files
outdir = 'nwm_oper_data'
### lcoation to store full downloaded NWM files temporarily
tmpdir = 'workspace'

######################################
### Functions
######################################
### function of check for existence of files for specific date
def checkForFiles(d):
	fileChannel = 'NEUS_'+d+'_nwm.t12z.analysis_assim.channel_rt.tm00.conus.nc'
	fileLand = 'NEUS_'+d+'_nwm.t12z.analysis_assim.land.tm00.conus.nc'
	savedFiles = os.listdir(outdir)
	# exit quietly if files already exist
	return fileChannel in savedFiles and fileLand in savedFiles

### function to find index of the closest value in an array
def findIdxOfNearestValue(array, value):
	array = np.asarray(array)
	idx = (np.abs(array - value)).argmin()
	return idx

### function to download NWM model output
def downloadNWM(ftype,day,hour='12',lookback='00',destdir='./'):
	'''Download NWM file.
		ftype : options include channel_rt, land
		day  : string date in format YYYYMMDD
		hour : hour to get file for as string HH
		destdir : directory to write data to
	'''
	fname = 'nwm.t'+hour+'z.analysis_assim.'+ftype+'.tm'+lookback+'.conus.nc'
	#cmd = 'wget -q -P '+destdir+' https://nomads.ncep.noaa.gov/pub/data/nccf/com/nwm/prod/nwm.'+day+'/analysis_assim/'+fname
	cmd = 'wget -q -P '+destdir+' ftp://ftpprd.ncep.noaa.gov/pub/data/nccf/com/nwm/prod/nwm.'+day+'/analysis_assim/'+fname
	res = os.system(cmd)
	return fname

### function to remove NWM file
def removeNWM(ftype,day,hour='12',lookback='00',locdir='./'):
	'''Remove NWM file.
		ftype : options include channel_rt, land
		day  : string date in format YYYYMMDD
		hour : hour to get file for as string HH
		locdir : directory where file exists
	'''
	fname = 'nwm.t'+hour+'z.analysis_assim.'+ftype+'.tm'+lookback+'.conus.nc'
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

### Date to retrieve analysis data
if len(sys.argv)==1:
	# current day
	YYYYMMDD = datetime.datetime.today().strftime('%Y%m%d')
else:
	# provided day from command line argument
	YYYYMMDD = sys.argv[1] if (type(sys.argv[1]) is str) else str(sys.argv[1])

### Check if files already exist
filesExist = checkForFiles(YYYYMMDD)
if filesExist: sys.exit()

### loop through days between start and end dates
sdate = YYYYMMDD
edate = YYYYMMDD
thisdate = sdate
while thisdate <= edate:

	######################################
	### CHANNEL file does not contain auxiliary coordinates. We do not subset the file.
	######################################
	ncfilename = downloadNWM('channel_rt',thisdate,hour='12',lookback='00',destdir=tmpdir)
	ncfilename_out = 'NEUS_'+thisdate+'_'+ncfilename
	# since this file doesn't have auxiliary coordinates, can't crop the file
	#subset_region = "-X "+str(ll_lon)+","+str(ur_lon)+","+str(ll_lat)+","+str(ur_lat)
	#subset_vars = "-v "+",".join(vars_channel)
	#crop_command = "ncks "+subset_region+" "+subset_vars+" "+tmpdir+ncfilename+" -O "+outdir+ncfilename_out
	#res = os.system(crop_command)
	# not cropping, just copying the full file into place
	rsync_command = 'rsync -a '+tmpdir+ncfilename+' '+outdir+ncfilename_out
	res = os.system(rsync_command)
	removeNWM('channel_rt',thisdate,hour='12',lookback='00',locdir=tmpdir)

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
	ncfilename = downloadNWM('land',thisdate,hour='12',lookback='00',destdir=tmpdir)
	ncfilename_out = 'NEUS_'+thisdate+'_'+ncfilename
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
	subset_vars = "-v "+",".join(vars_land)
	crop_command = "ncks "+subset_region+" "+subset_vars+" "+tmpdir+ncfilename+" -O "+outdir+ncfilename_out
	res = os.system(crop_command)
	removeNWM('land',thisdate,hour='12',lookback='00',locdir=tmpdir)

	######################################
	# update thisdate
	dt_date = datetime.datetime.strptime(thisdate,'%Y%m%d')
	dt_next = dt_date + datetime.timedelta(days=1)
	thisdate = dt_next.strftime('%Y%m%d')

### Make sure files now exist
filesExist = checkForFiles(YYYYMMDD)
if not filesExist: sys.exit('ERROR: files for '+YYYYMMDD+' were not downloaded')

