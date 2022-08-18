'''Create NWM drought indices.

	Create maps of NWM soil moisture and streamflow drought indices for a given day.
	Maps are used at: https://nedews.nrcc.cornell.edu/

	1. calculate 1-, 7-, 14-, 28-day averages of data for each year, forming a time series for full NWM period (1979-2020).
	2. calculate 1-, 7-, 14-, 28-day averages of data for given date.
	3. calculate percentiles from data in 1) and 2), using empirical methods.
	4. create map of percentiles, color-coded by USDM drought levels.

	This script accepts up to 2 arguments:
	variable - either 'streamflow' or 'SOIL_M' (required)
	date - date to analyze, in format YYYYMMDD (defaults to current date if not provided)

	See "User settings" section to set necessary variables:
		clim_year_range : tuple : starting and ending years used for climatological reference
		indir_retro : str : directory containing NWM retrospective model output files
		indir_oper : str : directory containing NWM operational model output files
		outdir : str : directory containing output map image products
		state_list : list : list of state names. These state borders will be displayed on map.
		bbox_keys : list : list of regions run separate maps for. Bounding boxes
			for each region is provided from these keys in getBbox function.
		miss : int : missing value identifier

	Usage:
		python scriptName variable date

	bnb2
'''
import os,sys
import copy
import datetime
import numpy as np
from netCDF4 import Dataset
import pyproj
import cartopy.crs as ccrs
from cartopy import feature
import fiona
from shapely.geometry import shape, MultiLineString, MultiPolygon
from matplotlib.patches import Polygon

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from MPLColorHelper import MplColorHelper

### must set PROJ_LIB manually for basemap to work ... should find out where to auto-activate
### in conda environment
#os.environ["PROJ_LIB"]="/home/bnb2/anaconda3/envs/nrcc-nedews/lib/python2.7/site-packages/pyproj/data"
os.environ["PROJ_LIB"]="/home/bnb2/anaconda3/envs/nwm-test/lib/python2.7/site-packages/pyproj/data"
from mpl_toolkits.basemap import Basemap

######################################
### User settings for subsetting datasets
######################################
#clim_year_range = ('1993','2018')
if datetime.datetime.today().strftime('%m%d')>='0315':
	clim_year_range = ('1979','2020')
else:
	clim_year_range = ('1980','2020')
### location of model output files
indir_retro = 'nwm_retro_data/'
indir_oper = 'nwm_oper_data/'
### location of output png files
outdir = 'nwm_drought_indicator_output/'
### state list
state_list = ['West Virginia','Maine','Massachusetts','Pennsylvania','Connecticut','Rhode Island',
	'New Jersey','New York','Delaware','Maryland','New Hampshire','Vermont']
### image bboxs to create
bbox_keys = ['ne','nedews','ny','vt','me','nh','ma','ct','ri']
### missing value (not scaled)
miss = -999900

######################################
### Variable to use from arguments list
######################################
if sys.argv[1] in ['SOIL_M','streamflow']:
	varname = sys.argv[1]
else:
	sys.exit('invalid varname provided')

######################################
### Dates to retrieve analysis data
######################################
if len(sys.argv)<3:
	# current day
	YYYYMMDD = datetime.datetime.today().strftime('%Y%m%d')
else:
	# provided day from command line argument
	YYYYMMDD = sys.argv[2] if (type(sys.argv[2]) is str) else str(sys.argv[2])

### determine summaries to perform, based on variable
# streamflow: 1,7,14,28-day lookbacks
if varname=='streamflow': summary_lengths = [1,7,14,28]
#if varname=='streamflow': summary_lengths = [1]
# SOIL_M: 1-day
if varname=='SOIL_M': summary_lengths = [1]
### modify outdir, adding another directory for this date and method
outdirWithFolder = outdir+YYYYMMDD+'_method1/'

### Adjust clim_year_range for streamflow, if month is January.
### This is necessary, since lookbacks can not go into 1978, since no data.
### Therefore, if it is January, limit the climatology to start in 1980.
### NOTE: 20220207 this is no longer necessary as clim_year_range is adjusted above for today's date
#if varname=='streamflow' and YYYYMMDD[4:6]=='01': clim_year_range = ('1980','2020')

######################################
### do test to see if nc file exists for this date. If not, exit with message.
######################################
if varname=='SOIL_M':
	ncfilename = 'NEUS_'+YYYYMMDD+'_nwm.t12z.analysis_assim.land.tm00.conus.nc'
if varname=='streamflow':
	ncfilename = 'NEUS_'+YYYYMMDD+'_nwm.t12z.analysis_assim.channel_rt.tm00.conus.nc'
ncFileExistsForDate = os.path.exists(indir_oper+ncfilename)
if not ncFileExistsForDate: sys.exit('nc file does not exist for '+YYYYMMDD)

######################################
### do test to see if png files already created. If so, analysis has already been performed, exit silently.
######################################
if varname=='SOIL_M':
	pngfilename = 'SOIL_M-1day-lev0.png'
if varname=='streamflow':
	pngfilename = 'streamflow-1day.png'
pngFileExistsForDate = os.path.exists(outdirWithFolder+pngfilename)
if pngFileExistsForDate: sys.exit()

######################################
### Functions
######################################
def getBbox(s):
	bbox = None
	#m = Basemap(llcrnrlat=37.0,urcrnrlat=48.0,llcrnrlon=-83.0,urcrnrlon=-66.5,resolution='h')
	if s=='ne': bbox=[-83.0, 37.0, -66.5, 48.0]
	if s=='nedews': bbox=[-80.2, 40.2, -66.6, 47.7]
	#if s=='ny': bbox=[-79.90, 40.45, -71.80, 45.05]
	if s=='ny': bbox=[-80.50, 40.40, -71.10, 45.20]
	#if s=='vt': bbox=[-74.00, 42.50, -71.20, 45.25]
	if s=='vt': bbox=[-74.00, 42.50, -71.20, 45.70]
	#if s=='me': bbox=[-72.00, 42.75, -66.85, 47.60]
	if s=='me': bbox=[-72.00, 42.75, -66.35, 48.10]
	#if s=='nh': bbox=[-72.75, 42.50, -70.25, 45.50]
	if s=='nh': bbox=[-73.10, 42.40, -69.90, 45.60]
	#if s=='ma': bbox=[-73.75, 41.20, -69.75, 43.00]
	if s=='ma': bbox=[-73.75, 41.20, -69.75, 43.40]
	#if s=='ct': bbox=[-73.75, 40.75, -71.25, 42.25]
	if s=='ct': bbox=[-74.00, 40.75, -71.25, 42.50]
	#if s=='ri': bbox=[-72.50, 41.00, -70.50, 42.25]
	if s=='ri': bbox=[-72.50, 41.00, -70.50, 42.50]
	return bbox

def getDatasetName(v):
	'''Get dataset name that contains given variable.
		v : variable to analyze.
	'''
	dsname = ''
	if v in ['streamflow','qBucket']: dsname='CHRTOUT'
	if v in ['SOIL_M','SOIL_W']: dsname='LDASOUT'
	return dsname

def GetRelativeStreamflowColor(info,data):
	key = info['COMID']
	if key in data:
		#print data[key],CMap.get_rgb(data[key])
		return CMap.get_rgb(data[key])
	return (1.0, 1.0, 1.0, 1.0)
	#return (0.0, 1.0, 0.0, 1.0)

def GetStreamflowColor(info,data):
	c = (0.0, 1.0, 0.0, 1.0)
	key = info['COMID']
	c = CMap.get_rgb(data[key])
	return c

def GetRelativeStreamflowColor2(info,data,levs,cols):
	key = info['COMID']
	if key in data:
		for idx in range(len(levs)-1):
			if data[key]>=levs[idx] and data[key]<levs[idx+1]:
				return cols[idx]
	return (1.0, 1.0, 1.0, 1.0)
	#return (0.0, 1.0, 0.0, 1.0)

######################################
### MAIN
######################################
### Create input and destination directories if they do not exist.
outdir = outdir if outdir[-1]=='/' else outdir+'/'
outputDirExists = os.path.exists(outdir)
if not outputDirExists: res = os.system('mkdir -p '+outdir)
indir_retro = indir_retro if indir_retro[-1]=='/' else indir_retro+'/'
tmpDirExists = os.path.exists(indir_retro)
if not tmpDirExists: res = os.system('mkdir -p '+indir_retro)
indir_oper = indir_oper if indir_oper[-1]=='/' else indir_oper+'/'
tmpDirExists = os.path.exists(indir_oper)
if not tmpDirExists: res = os.system('mkdir -p '+indir_oper)

### dataset type for selected variable
dstype = getDatasetName(varname)

### loop through averaging periods
for per in summary_lengths:

	######################################
	### Create climatology for this averaging period.
	### 1) Loop through each year
	### 2) In each year:
	###	- calculate period averages over period of interest (period_ave).
	###	- save period averages to a list (data_clim). These will be used to
	###	calculate percentiles later.
	######################################
	data_clim = []
	sdate = clim_year_range[0]+YYYYMMDD[4:]
	edate = clim_year_range[1]+YYYYMMDD[4:]
	thisdate = sdate
	while thisdate <= edate:

		######################################
		### calculate average conditions over period
		######################################
		perdate = copy.deepcopy(thisdate)
		data_period = []
		for i in range(per):
			### change to day i within period
			dt_date = datetime.datetime.strptime(thisdate,'%Y%m%d')
			dt_next = dt_date - datetime.timedelta(days=i)
			perdate = dt_next.strftime('%Y%m%d')
			### extract variable for this data and append to list
			ncfilename = 'NEUS_'+perdate+'1200.'+dstype+'_DOMAIN1.comp'
			ncfile = Dataset(indir_retro+ncfilename,'r')
			if varname=='SOIL_M' or varname=='SOIL_W': data_period.append(ncfile.variables[varname][0,:,:,:])
			if varname=='streamflow' or varname=='qBucket': data_period.append(ncfile.variables[varname][:])
			ncfile.close()
		data_period = np.array(data_period)
		period_ave = np.average(data_period,axis=0)
		del data_period

		######################################
		### save period average for this year to clim list
		######################################
		#print 'period_ave shape for '+thisdate+', period lenth '+str(per)+' : ',period_ave.shape
		data_clim.append(period_ave[:])
		del period_ave

		######################################
		### update thisdate
		######################################
		thisyear = thisdate[:4]
		nextyear = int(thisyear) + 1
		thisdate = str(nextyear)+thisdate[4:]

	### to numpy array for use with built-in numpy/scipy methods.
	data_clim = np.array(data_clim)
	if varname=='SOIL_M': data_clim = np.ma.masked_where(data_clim<0, data_clim)
	#print 'data_clim shape for period length '+str(per)+' : ',data_clim.shape

	######################################
	### calculate average conditions over period for target event
	######################################
	thisdate = copy.deepcopy(YYYYMMDD)
	data_period = []
	for i in range(per):
		### change to day i within period
		dt_date = datetime.datetime.strptime(thisdate,'%Y%m%d')
		dt_next = dt_date - datetime.timedelta(days=i)
		perdate = dt_next.strftime('%Y%m%d')
		### extract variable for this data and append to list
		if varname=='SOIL_M':
			ncfilename = 'NEUS_'+perdate+'_nwm.t12z.analysis_assim.land.tm00.conus.nc'
		if varname=='streamflow':
			ncfilename = 'NEUS_'+perdate+'_nwm.t12z.analysis_assim.channel_rt.tm00.conus.nc'
		ncfile = Dataset(indir_oper+ncfilename,'r')
		proj4_string = ncfile.getncattr('proj4')
		if varname=='streamflow' or varname=='qBucket': feature_idsa = np.array(ncfile.variables['feature_id'])
		if varname=='SOIL_M' or varname=='SOIL_W': x = ncfile.variables['x'][:]
		if varname=='SOIL_M' or varname=='SOIL_W': y = ncfile.variables['y'][:]
		if varname=='SOIL_M' or varname=='SOIL_W': data_period.append(ncfile.variables[varname][0,:,:,:])
		if varname=='streamflow' or varname=='qBucket': data_period.append(ncfile.variables[varname][:])
		ncfile.close()
	data_period = np.array(data_period)
	data_event = np.average(data_period,axis=0)
	if varname=='SOIL_M': data_event = np.ma.masked_where(data_event<0, data_event)
	del data_period
	#print 'data_event shape for '+thisdate+', period length '+str(per)+' : ',data_event.shape

	### Find stream reaches that have the same value for all years.
	### At least some of these cases appear to be lake locations.
	### These reaches will be removed prior to map creation, from variables that need it.
	if varname=='streamflow':
		reachesToDelete = np.argwhere( np.min(data_clim,axis=0)==np.max(data_clim,axis=0) )

	# There are 42 years in data_clim (for NWM v2.1) and 1 current event year. We add 1 to the numerator
	# and denominator for the current year.
	# Percentiles are calculated as rank/(n+1).
	# In numerator, 1 is added to adjust rank for the data event.
	# In denominator, an additional 1 is added for the data event.
	if varname=='SOIL_M':
		event_percentiles1 = ((data_clim<data_event).sum(axis=0)+1)/float(data_clim.shape[0]+2)
		event_percentiles2 = ((data_clim<=data_event).sum(axis=0)+1)/float(data_clim.shape[0]+2)
		event_percentiles = (event_percentiles1 + event_percentiles2)/2.
	if varname=='streamflow':
		event_percentiles1 = ((data_clim<data_event).sum(axis=0)+1)/float(data_clim.shape[0]+2)
		event_percentiles2 = ((data_clim<=data_event).sum(axis=0)+1)/float(data_clim.shape[0]+2)
		event_percentiles = (event_percentiles1 + event_percentiles2)/2.

	for bbox_key in bbox_keys:
		#print bbox_key

		bbox = getBbox(bbox_key)

		### plot soil moisture percentiles
		if varname=='SOIL_M' or varname=='SOIL_W':
			input_shapefile = 'us_shapefile/st99_d00'
			varlen=4
			for varidx in range(varlen):

				######################################
				### Plot data on map
				######################################
				SMALL_SIZE = 4
				MEDIUM_SIZE = 6
				BIGGER_SIZE = 8

				plt.rc('font', size=MEDIUM_SIZE)          # controls default text sizes
				plt.rc('axes', titlesize=SMALL_SIZE)     # fontsize of the axes title
				plt.rc('axes', labelsize=MEDIUM_SIZE)    # fontsize of the x and y labels
				plt.rc('xtick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
				plt.rc('ytick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
				plt.rc('legend', fontsize=SMALL_SIZE)    # legend fontsize
				plt.rc('figure', titlesize=BIGGER_SIZE)  # fontsize of the figure title

				plt.figure(figsize=(4,4))
				m = Basemap(llcrnrlat=bbox[1],urcrnrlat=bbox[3],llcrnrlon=bbox[0],urcrnrlon=bbox[2],resolution='h')

				### load the shapefiles, draw on map
				ax = plt.gca()

				world_shp_info = m.readshapefile('world_shapefile/CNTR_2014_10M_SH/Data/CNTR_RG_10M_2014','world',drawbounds=False)
				for shapedict,state in zip(m.world_info, m.world):
					if shapedict['CNTR_ID'] not in ['CA', 'MX']: continue
					poly = Polygon(state,facecolor='white',edgecolor='white')
					ax.add_patch(poly)

				usa_shape_info = m.readshapefile(input_shapefile, name='states', drawbounds=False)
				for shapedict,state in zip(m.states_info, m.states):
					if shapedict['NAME'] in state_list: continue
					poly = Polygon(state,facecolor='white',edgecolor='white')
					ax.add_patch(poly)
				for shapedict,state in zip(m.states_info, m.states):
					if shapedict['NAME'] not in state_list: continue
					poly = Polygon(state,facecolor='None',edgecolor='black',linewidth=0.5)
					ax.add_patch(poly)

				### create 2D grid from 1D lat and lon
				x_mesh, y_mesh = np.meshgrid(x, y)

				### projections: convert from lcc to latlong
				p1 = pyproj.Proj(proj4_string)
				p2 = pyproj.Proj(proj='latlong', datum='WGS84')
				lon_mesh,lat_mesh = pyproj.transform(p1,p2,x_mesh,y_mesh)

				clevs = [0,2,5,10,20,30,70,80,90,95,98,100]
				clevs_cmap = [0,2,5,10,20,30,70,80,90,95,98,100]
				ccols_cmap = [
					(102/255.,19/255.,5/255.),
					(216/255.,45/255.,27/255.),
					(236/255.,178/255.,54/255.),
					(244/255.,213/255.,137/255.),
					(255/255.,251/255.,91/255.),
					(255/255.,255/255.,255/255.),
					(140/255.,205/255.,239/255.),
					(0/255.,191/255.,255/255.),
					(29/255.,144/255.,255/255.),
					(65/255.,105/255.,225/255.),
					(0/255.,0/255.,255/255.),
					]
				cmap_data = LinearSegmentedColormap.from_list("cmap_data",ccols_cmap)

				cs = m.contourf(lon_mesh,lat_mesh,event_percentiles[:,varidx,:]*100.,clevs_cmap,colors=ccols_cmap)

				#m.drawlsmask(land_color='None',ocean_color='white',lakes=True)

				# add colorbar
				cb = m.colorbar(cs,"bottom", size="5%", pad="2%")
				cb.set_ticks(clevs_cmap)
				#cb.set_label('Percentile')

				if varidx==0: depth='0-10 cm'
				if varidx==1: depth='10-40 cm'
				if varidx==2: depth='40-100 cm'
				if varidx==3: depth='100-200 cm'

				if per==1:
					titleString = 'NWM Soil Moisture Percentile'+os.linesep+\
						'Depth: '+depth+os.linesep+\
						'Date: '+'/'.join([str(int(YYYYMMDD[4:6])),str(int(YYYYMMDD[6:])),YYYYMMDD[:4]])
				else:
					titleString = 'NWM Soil Moisture Percentile'+os.linesep+\
						'Depth: '+depth+os.linesep+\
						str(per)+'-Day Ave ending '+\
						'/'.join([str(int(YYYYMMDD[4:6])),str(int(YYYYMMDD[6:])),YYYYMMDD[:4]])

				ax.text(0.05, 0.95, titleString, transform=ax.transAxes, fontsize=5,
					bbox=dict(facecolor='white', edgecolor='white'),
					verticalalignment='top')

				### create outdir directory path if it doesn't exist
				outputDirExists = os.path.exists(outdirWithFolder)
				if not outputDirExists: res = os.system('mkdir -p '+outdirWithFolder)
				### save fig
				if bbox_key!='ne':
					output_filename = varname+'-'+str(per)+'day-lev'+str(varidx)+'-'+bbox_key+'.png'
				else:
					output_filename = varname+'-'+str(per)+'day-lev'+str(varidx)+'.png'
				plt.savefig(outdirWithFolder+output_filename, bbox_inches='tight', pad_inches=0.05, transparent=False, dpi=300)
				plt.close()

		### plot streamflow percentiles
		if varname=='streamflow':
			input_shapefile = 'us_shapefile/st99_d00.shp'
			inshape = 'NHDPlus/NHDFlowline_Network_'+bbox_key+'.shp'
			shp_10k = fiona.open(inshape, 'r')
			mp_10k = MultiLineString([shape(line['geometry']) for line in shp_10k])
			shp_states = fiona.open(input_shapefile, 'r')
			mp_states = MultiPolygon([shape(line['geometry']) for line in shp_states])
			shpProj = ccrs.PlateCarree()
			varlen=1
			for varidx in range(varlen):

				# must remove reaches that have constant value for all years.
				# These were found above.
				feature_idsa_clean = np.delete(feature_idsa,reachesToDelete,axis=0)
				event_percentiles_clean = np.delete(event_percentiles,reachesToDelete,axis=0)

				streamflow = {key: value for (key, value) in zip(feature_idsa_clean, event_percentiles_clean[:]*100.)}

				######################################
				### Plot data on map
				######################################
				clevs = [0,2,5,10,20,30,70,80,90,95,98,100]
				clevs_cmap = [0,2,5,10,20,30,70,80,90,95,98,100]
				ccols_cmap = [
					(102/255.,19/255.,5/255.),
					(216/255.,45/255.,27/255.),
					(236/255.,178/255.,54/255.),
					(244/255.,213/255.,137/255.),
					(255/255.,251/255.,91/255.),
					#(255/255.,255/255.,255/255.),
					(235/255.,235/255.,235/255.),
					(140/255.,205/255.,239/255.),
					(0/255.,191/255.,255/255.),
					(29/255.,144/255.,255/255.),
					(65/255.,105/255.,225/255.),
					(0/255.,0/255.,255/255.),
					]
				cmap_data = LinearSegmentedColormap.from_list("cmap_data",ccols_cmap)
				CMap = MplColorHelper(cmap_data, clevs[0], clevs[-1])

				flowline_relativestreamflow_color = [GetRelativeStreamflowColor2(line['properties'],streamflow,clevs_cmap,ccols_cmap) for line in shp_10k]

				proj = ccrs.PlateCarree()

				fig = plt.figure()
				fig.subplots_adjust(bottom=0.2)

				if varname=='streamflow':
					if per==1:
						titleString = 'NWM Streamflow Percentile'+os.linesep+'Date: '+\
							'/'.join([str(int(YYYYMMDD[4:6])),str(int(YYYYMMDD[6:])),YYYYMMDD[:4]])
					else:
						titleString = 'NWM Streamflow Percentile'+os.linesep+str(per)+'-Day Ave ending '+\
							'/'.join([str(int(YYYYMMDD[4:6])),str(int(YYYYMMDD[6:])),YYYYMMDD[:4]])
				ax = plt.axes(projection = proj)

				ax.set_extent([bbox[0],bbox[2],bbox[1],bbox[3]])

				### add streamflow percentiles to map
				ax.add_feature(feature.ShapelyFeature(mp_10k, shpProj),
					facecolor=flowline_relativestreamflow_color,edgecolor=flowline_relativestreamflow_color,linewidth=0.3,zorder=2)
				ax.add_feature(feature.ShapelyFeature(mp_states, shpProj),
					facecolor='None',edgecolor='black',linewidth=0.5,zorder=1)

				# place a text box in upper left in axes coords
				ax.text(0.05, 0.95, titleString, transform=ax.transAxes, fontsize=6,
					bbox=dict(facecolor='white', edgecolor='white'),
					verticalalignment='top')

				ax_legend = fig.add_axes([0.3, 0.17, 0.4, 0.03], zorder=3)
				ticks = np.array([2,5,10,20,30,70,80,90,95,98])
				cb = matplotlib.colorbar.ColorbarBase(ax_legend, cmap=cmap_data, ticks=ticks, norm=matplotlib.colors.BoundaryNorm(clevs_cmap, cmap_data.N), orientation='horizontal')
				cb.ax.set_xticklabels([str(i) for i in ticks])
				cb.ax.tick_params(labelsize=4)

				### create outdir directory path if it doesn't exist
				outputDirExists = os.path.exists(outdirWithFolder)
				if not outputDirExists: res = os.system('mkdir -p '+outdirWithFolder)
				### save fig
				if bbox_key!='ne':
					output_filename = varname+'-'+str(per)+'day-'+bbox_key+'.png'
				else:
					output_filename = varname+'-'+str(per)+'day.png'
				plt.savefig(outdirWithFolder+output_filename, bbox_inches='tight', pad_inches=0.05, transparent=True, dpi=600)
				plt.close()

### copy most recent files to 'current_method1' directory
### 1. find most recent folder containing all expected files (combination of soil moisture and streamflow)
### 2. rsync files from most recent folder to 'current_method1' folder
outdirList = os.listdir(outdir)
# list of existing output directories, by day
dailyOutputList = [ item for item in outdirList if item.split('_')[0][:2]=='20' and item.split('_')[1]=='method1' ]
# filter list of output directories to only contain directories that have all expected output files
dailyOutputList = [ item for item in dailyOutputList if len(os.listdir(outdir+item))==72 ]
# populate the 'current' directory with maps from the latest complete directory
if len(dailyOutputList)!=0:
	dailyOutputList.sort()
	latestDir = outdir+dailyOutputList[-1]+'/'
	currentDir = outdir+'current_method1/'
	currentDirExists = os.path.exists(currentDir)
	if not currentDirExists: res = os.system('mkdir -p '+currentDir)
	cmd = 'rsync -a '+latestDir+' '+currentDir
	res = os.system(cmd)

