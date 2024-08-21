#####################
# Project structure #
#####################
root_dir = ''

lib_dir = root_dir + '/lib'
writable_dir = root_dir + '/nwm_drought_volume'

us_shp_dir = writable_dir + '/us_shapefile'
nhdplus_dir = writable_dir + '/NHDPlus'

### location to store full downloaded NWM files temporarily
temp_dir = writable_dir + '/workspace'

### location to store subset NWM files
retro_data_dir = writable_dir + '/nwm_retro_data'
oper_data_dir = writable_dir + '/nwm_oper_data'

output_dir = writable_dir + '/nwm_drought_indicator_output'
#####################


### Region definitions. These are used to create filtered and cropped NHDPlus data files.
regions = {
	'ne': [-83.0, 37.0, -66.5, 48.0],
	'nedews': [-80.2, 40.2, -66.6, 47.7],
	'ny': [-80.50, 40.40, -71.10, 45.20],
	'vt': [-74.00, 42.50, -71.20, 45.70],
	'me': [-72.00, 42.75, -66.35, 48.10],
	'nh': [-73.10, 42.40, -69.90, 45.60],
	'ma': [-73.75, 41.20, -69.75, 43.40],
	'ct': [-74.00, 40.75, -71.25, 42.50],
	'ri': [-72.50, 41.00, -70.50, 42.50],
	'wv':  [-83.00, 37.00, -77.50, 40.80]
}

# Product definitions. These are looped over for configuration info when creating product maps
products = [{
  'varname': 'SOIL_M',
	'varlen': 4,
	### soil moisture summary lengths (typically 1, just comparing current soil moisture to climatology)
  'summary_lengths': [1],
  'dstype': 'LDASOUT',
  'clevs_cmap': [0,2,5,10,20,30,70,80,90,95,98,100],
	'ccols_cmap': [
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
		(0/255.,0/255.,255/255.)
	]
}, {
  'varname': 'streamflow',
	'varlen': 1,
	### streamflow summary lengths (lookback in days)
  'summary_lengths': [1,7,14,28],
  'dstype': 'CHRTOUT',
  'clevs_cmap': [0,2,5,10,20,30,70,80,90,95,98,100],
  'ccols_cmap': [
		(102/255.,19/255.,5/255.),
		(216/255.,45/255.,27/255.),
		(236/255.,178/255.,54/255.),
		(244/255.,213/255.,137/255.),
		(255/255.,251/255.,91/255.),
		(235/255.,235/255.,235/255.),
		(140/255.,205/255.,239/255.),
		(0/255.,191/255.,255/255.),
		(29/255.,144/255.,255/255.),
		(65/255.,105/255.,225/255.),
		(0/255.,0/255.,255/255.)
	]
}]

# lower-left, upper-right corners of region of interest. Used to crop LDASOUT and land files.
ll_lon = -83.00
ll_lat = 37.00
ur_lon = -65.00
ur_lat = 48.10

# Number of retro days to retrieve
# # NOTE this will include two days after YYYYMMDD and remainder of days before YYYYMMDD, so minimum value is 3 for summary length of 1.
# # Example: If YYYYMMDD='20220815' and numdays_in_period=7, then the following dates are retrived for each year: ['0811','0812','0813','0814','0815','0816','0817']
# # Data are rotated off as to only maintain a data window of this size, relative to current date.
# # Use the highest value in 'streamflow_summary_lengths' or 'soilm_summary_lengths' and add a few days as cushion in case data source is temporarily unavailable.
numdays_in_period = 33

# The files for 12Z become available after 9:30 AM ET.
hour='12'

# Use '00', not really sure what the file difference is
lookback='00'

# Used to determine which state shapes to add to maps
state_list = ['West Virginia', 'Maine', 'Massachusetts', 'Pennsylvania', 'Connecticut', 'Rhode Island', 'New Jersey', 'New York', 'Delaware', 'Maryland', 'New Hampshire', 'Vermont']