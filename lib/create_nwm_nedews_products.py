'''
	Create maps of NWM soil moisture and streamflow drought indices for a given day.
	Maps are used at: https://nedews.nrcc.cornell.edu/

	1. calculate 1-, 7-, 14-, 28-day averages of data for each year, forming a time series for full NWM period (1979-2020).
	2. calculate 1-, 7-, 14-, 28-day averages of data for given date.
	3. calculate percentiles from data in 1) and 2), using empirical methods.
	4. create map of percentiles, color-coded by USDM drought levels.

	orig bnb2, updated to python3 be99
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
from shapely.geometry import shape, MultiPolygon, Polygon
from operator import itemgetter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# Uses data value to determine color stream shape should be
def get_relative_streamflow_color(info, data, levs, cols):
	key = info['COMID']
	if key in data:
		for idx in range(len(levs)-1):
			if data[key] >= levs[idx] and data[key] < levs[idx+1]:
				return cols[idx]
	return (1.0, 1.0, 1.0, 1.0)

def add_colorbar(fig, clevs_cmap, cmap_data, labelsize):
	ax_legend = fig.add_axes([0.3, 0.17, 0.4, 0.03], zorder=3)
	cb = matplotlib.colorbar.ColorbarBase(ax_legend, cmap=cmap_data, ticks=clevs_cmap, norm=matplotlib.colors.BoundaryNorm(clevs_cmap, cmap_data.N), orientation='horizontal')
	cb.ax.set_xticklabels([str(i) for i in clevs_cmap])
	cb.ax.tick_params(labelsize=labelsize)

def add_titlebox(text, ax, fontsize):
	ax.text(0.05, 0.95, text, transform=ax.transAxes, fontsize=fontsize, bbox=dict(color='white'), verticalalignment='top')

def take_snapshots(ax, varname, varidx, per, out_dir, regions):
	# Loop regions to take zoomed in snapshots
	for bbox_key in regions.keys():
		# Get bbox and rezoom plot
		bbox = regions[bbox_key]
		ax.set_extent([bbox[0],bbox[2],bbox[1],bbox[3]])

		# Construct output filename
		fname_parts = [f'{varname}-{str(per)}day']
		if varname=='SOIL_M':
			fname_parts.append(f'-lev{str(varidx)}')
		if bbox_key != 'ne':
			fname_parts.append(f'-{bbox_key}')
		fname_parts.append('.png')
		output_filename = ''.join(fname_parts)

		# Save figure
		plt.savefig(os.path.join(out_dir, output_filename), bbox_inches='tight', pad_inches=0.05, dpi=300)


def create_products(config, YYYYMMDD, syear, dataset_type_dict):
	varname, varlen, summary_lengths, dstype, clevs_cmap, ccols_cmap = itemgetter('varname', 'varlen', 'summary_lengths', 'dstype', 'clevs_cmap', 'ccols_cmap')(dataset_type_dict)
	
	# Make sure output dir for day exists
	day_out_dir = os.path.join(config.output_dir, f'{YYYYMMDD}_method1')
	if not os.path.exists(day_out_dir): os.mkdir(day_out_dir)

	# Check if operational data is available and if analysis has already run
	if varname=='SOIL_M':
		ncfilename = f'NEUS_{YYYYMMDD}_nwm.t12z.analysis_assim.land.tm00.conus.nc'
		pngfilename = 'SOIL_M-1day-lev0.png'
	elif varname=='streamflow':
		ncfilename = f'NEUS_{YYYYMMDD}_nwm.t12z.analysis_assim.channel_rt.tm00.conus.nc'
		pngfilename = 'streamflow-1day.png'
	ncfile_exists = os.path.exists(os.path.join(config.oper_data_dir, ncfilename))
	if not ncfile_exists:
		# Exit with message if data doesn't exist
		sys.exit(f'nc file does not exist for {YYYYMMDD}')
	pngfile_exists = os.path.exists(os.path.join(day_out_dir, pngfilename))
	if pngfile_exists:
		# Exit silently if analysis has already run
		sys.exit()


	###############################################
	### SET UP COMMON VARIABLES FOR EFFICIENCY ###
	###############################################
	
	# Define date as string for use in figure titles later
	date_str = '/'.join([str(int(YYYYMMDD[4:6])),str(int(YYYYMMDD[6:])),YYYYMMDD[:4]])

	# Define projection of shapefiles
	shp_proj = ccrs.PlateCarree()

	if varname == 'streamflow':
		# Load streamflow shapefile
		inshape = os.path.join(config.nhdplus_dir, f'NHDFlowline_Network.shp')
		shp_10k = fiona.open(inshape, 'r')
	elif varname == 'SOIL_M':
		# Create mask to cover data outside of area of interest
		mask_polygon = Polygon([
			(config.ll_lon, config.ll_lat),
			(config.ll_lon, config.ur_lat),
			(config.ur_lon, config.ur_lat),
			(config.ur_lon, config.ll_lat),
			(config.ll_lon, config.ll_lat)
		])

	# Load states shapefile and make list of states of interest, unmasking them if SOIL_M
	states_shapefile = os.path.join(config.us_shp_dir, 'st99_d00.shp')
	states_shp = fiona.open(states_shapefile, 'r')
	state_border_polygons = []
	for feat in states_shp:
		if feat['properties']['NAME'] in config.state_list or varname=='streamflow':
			state_shp = shape(feat['geometry'])
			state_border_polygons.append(state_shp)
			if varname == 'SOIL_M':
				mask_polygon = mask_polygon.difference(state_shp)
	state_border_polygons = MultiPolygon(state_border_polygons)

	# Define colors and ticks
	cmap_data = LinearSegmentedColormap.from_list("cmap_data",ccols_cmap)

	# Figure font sizes
	SMALL_SIZE = 4
	MEDIUM_SIZE = 6
	BIGGER_SIZE = 8

	###############################################

	# Loop through averaging periods
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
		sdate = f'{syear}{YYYYMMDD[4:]}'
		edate = f'2020{YYYYMMDD[4:]}'
		this_date = sdate
		while this_date <= edate:
			# Calculate average conditions over period
			per_date = copy.deepcopy(this_date)
			data_period = []
			for i in range(per):
				# Change to day i within period
				if this_date[4:] == '0229' and int(this_date[:4]) % 4 != 0:
					dt_date = datetime.datetime.strptime(f'{this_date[:4]}0301','%Y%m%d')
				else:
					dt_date = datetime.datetime.strptime(this_date,'%Y%m%d')
				dt_next = dt_date - datetime.timedelta(days=i)
				per_date = dt_next.strftime('%Y%m%d')
				
				# Extract variable for this data and append to list
				ncfilename = f'NEUS_{per_date}1200.{dstype}_DOMAIN1'
				ncfile = Dataset(os.path.join(config.retro_data_dir, ncfilename),'r')
				if varname=='SOIL_M':
					data_period.append(ncfile.variables[varname][0,:,:,:])
				elif varname=='streamflow':
					data_period.append(ncfile.variables[varname][:])
				ncfile.close()
			
			# Convert to np array to average period, add averages to climatology, delete old copies of data to save memory
			data_period = np.array(data_period)
			period_ave = np.average(data_period,axis=0)
			data_clim.append(period_ave[:])
			del data_period
			del period_ave

			# Increment this_date
			thisyear = this_date[:4]
			nextyear = int(thisyear) + 1
			this_date = str(nextyear)+this_date[4:]

		# Convert climatology to numpy array for use with built-in numpy/scipy methods.
		data_clim = np.array(data_clim)
		if varname=='SOIL_M': data_clim = np.ma.masked_where(data_clim<0, data_clim)

		# Calculate average conditions over period for target date
		this_date = copy.deepcopy(YYYYMMDD)
		data_period = []
		for i in range(per):
			# Change to day i within period
			dt_date = datetime.datetime.strptime(this_date,'%Y%m%d')
			dt_next = dt_date - datetime.timedelta(days=i)
			per_date = dt_next.strftime('%Y%m%d')

			# Extract variable for this data and append to list
			if varname=='SOIL_M':
				ncfilename = f'NEUS_{per_date}_nwm.t12z.analysis_assim.land.tm00.conus.nc'
			elif varname=='streamflow':
				ncfilename = f'NEUS_{per_date}_nwm.t12z.analysis_assim.channel_rt.tm00.conus.nc'
			ncfile = Dataset(os.path.join(config.oper_data_dir, ncfilename),'r')
			proj4_string = ncfile.getncattr('proj4')
			if varname=='SOIL_M':
				# Get x and y coords
				x = ncfile.variables['x'][:]
				y = ncfile.variables['y'][:]

				# Create 2D grid from 1D lat and lon
				x_mesh, y_mesh = np.meshgrid(x, y)

				data_period.append(ncfile.variables[varname][0,:,:,:])
			elif varname=='streamflow':
				# Remove features that do not exist in v3 data
				feature_idsa = np.array(ncfile.variables['feature_id'])
				data_period.append(ncfile.variables[varname][:])
			ncfile.close()
		
		# Convert to numpy array, average the period, delete old data copies
		data_period = np.array(data_period)
		data_event = np.average(data_period,axis=0)
		if varname=='SOIL_M': data_event = np.ma.masked_where(data_event<0, data_event)
		del data_period

		# Find stream reaches that have the same value for all years.
		# At least some of these cases appear to be lake locations.
		# These reaches will be removed prior to map creation, from variables that need it.
		if varname=='streamflow':
			reaches_to_delete = np.argwhere( np.min(data_clim,axis=0)==np.max(data_clim,axis=0) )

		# There are 42 years in data_clim (for NWM v3.0) and 1 current event year. We add 1 to the numerator
		# and denominator for the current year.
		# Percentiles are calculated as rank/(n+1).
		# In numerator, 1 is added to adjust rank for the data event.
		# In denominator, an additional 1 is added for the data event.
		if varname=='SOIL_M':
			event_percentiles1 = ((data_clim<data_event).sum(axis=0)+1)/float(data_clim.shape[0]+2)
			event_percentiles2 = ((data_clim<=data_event).sum(axis=0)+1)/float(data_clim.shape[0]+2)
			event_percentiles = (event_percentiles1 + event_percentiles2)/2.
		elif varname=='streamflow':
			event_percentiles1 = ((data_clim<data_event).sum(axis=0)+1)/float(data_clim.shape[0]+2)
			event_percentiles2 = ((data_clim<=data_event).sum(axis=0)+1)/float(data_clim.shape[0]+2)
			event_percentiles = (event_percentiles1 + event_percentiles2)/2.

		###########################
		### MAPPING BEGINS HERE ###
		###########################

		# Plot soil moisture percentiles
		if varname=='SOIL_M':
			# Transform projection from lcc to latlong
			p1 = pyproj.Proj(proj4_string)
			p2 = pyproj.Proj(proj='latlong', datum='WGS84')
			transformer = pyproj.Transformer.from_proj(p1,p2)
			lon_mesh,lat_mesh = transformer.transform(x_mesh,y_mesh)
			
			for varidx in range(varlen):
				# Set up figure
				plt.rc('font', size=MEDIUM_SIZE)          # controls default text sizes
				plt.rc('axes', titlesize=SMALL_SIZE)     # fontsize of the axes title
				plt.rc('axes', labelsize=MEDIUM_SIZE)    # fontsize of the x and y labels
				plt.rc('xtick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
				plt.rc('ytick', labelsize=SMALL_SIZE)    # fontsize of the tick labels
				plt.rc('legend', fontsize=SMALL_SIZE)    # legend fontsize
				plt.rc('figure', titlesize=BIGGER_SIZE)  # fontsize of the figure title

				fig = plt.figure()
				# fig = plt.figure(figsize=(4,4))
				fig.subplots_adjust(bottom=0.2)
				ax = plt.axes(projection=shp_proj)

				# Add soil moisture percentiles, mask, and state outlines to figure
				ax.contourf(lon_mesh,lat_mesh,event_percentiles[:,varidx,:]*100.,clevs_cmap,colors=ccols_cmap, zorder=1)
				ax.add_feature(feature.ShapelyFeature(mask_polygon, shp_proj), color='white',linewidth=0.5,zorder=2)
				ax.add_feature(feature.ShapelyFeature(state_border_polygons, shp_proj), facecolor='None',edgecolor='black',linewidth=0.5,zorder=3)

				# Add colorbar to figure
				add_colorbar(fig, clevs_cmap, cmap_data, SMALL_SIZE)

				# Add title to figure
				if varidx==0: depth='0-10 cm'
				elif varidx==1: depth='10-40 cm'
				elif varidx==2: depth='40-100 cm'
				elif varidx==3: depth='100-200 cm'
				if per==1:
					title_str = f'NWM Soil Moisture Percentile{os.linesep}Depth: {depth}{os.linesep}Date: {date_str}'
				else:
					title_str = f'NWM Soil Moisture Percentile{os.linesep}Depth: {depth}{os.linesep}{str(per)}-Day Ave ending {date_str}'
				add_titlebox(title_str, ax, 5)

				# Loop regions to take zoomed in snapshots
				take_snapshots(ax, varname, varidx, per, day_out_dir, config.regions)

				# Close the figure
				plt.close()

		# Plot streamflow percentiles
		elif varname=='streamflow':
			for varidx in range(varlen):
				###############
				### This section could be moved for efficiency or maybe incorporated into the streamflow_ids
				###   precalculated file, but streamflow is only calculated with varlen of 1, so this only 
				###   executes once. It is left here for code readability
				
				# Remove reaches that have constant value for all years. These were found above.
				feature_idsa_clean = np.delete(feature_idsa,reaches_to_delete,axis=0)
				event_percentiles_clean = np.delete(event_percentiles,reaches_to_delete,axis=0)
				streamflow = {key: value for (key, value) in zip(feature_idsa_clean, event_percentiles_clean[:]*100.)}
				
				###############

				# Place each stream shape into a key in flowline_relativestreamflow_color object where
				#   each key is a color definition. The result is [color]: list of shapes. This allows
				#   the shapes to quickly be added to the figure with the defined color. Adding individually
				#   is extremely slow and adding them like in the original script results in all shapes
				#   being the same color
				flowline_relativestreamflow_color = {}
				for line in shp_10k:
					color = get_relative_streamflow_color(line['properties'],streamflow,clevs_cmap,ccols_cmap)
					stream_shape = shape(line['geometry'])
					if color not in flowline_relativestreamflow_color:
						flowline_relativestreamflow_color[color] = []
					flowline_relativestreamflow_color[color].append(stream_shape)

				# Set up figure
				fig = plt.figure()
				fig.subplots_adjust(bottom=0.2)
				fig.set_facecolor('none')
				ax = plt.axes(projection = shp_proj)
				ax.set_facecolor('white')

				# Add streamflow percentiles and state outline to figure
				for color, shapes in flowline_relativestreamflow_color.items():
					ax.add_feature(feature.ShapelyFeature(shapes, shp_proj),	color=color, linewidth=0.3, zorder=2)
				ax.add_feature(feature.ShapelyFeature(state_border_polygons, shp_proj), facecolor='None', edgecolor='black', linewidth=0.5, zorder=1)

				# Add title to figure
				if per==1:
					title_str = f'NWM Streamflow Percentile{os.linesep}Date: {date_str}'
				else:
					title_str = f'NWM Streamflow Percentile{os.linesep}{str(per)}-Day Ave ending {date_str}'
				add_titlebox(title_str, ax, MEDIUM_SIZE)

				# Add colorbar to figure
				add_colorbar(fig, clevs_cmap, cmap_data, SMALL_SIZE)

				# Loop regions to take zoomed in snapshots
				take_snapshots(ax, varname, varidx, per, day_out_dir, config.regions)

				# Close the figure
				plt.close()