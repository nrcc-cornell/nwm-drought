'''Download shapefiles for NWM drought index maps.

	Download shapefiles for political boundaries and stream reach info.

	Three directories will be created, with shapefile contents:
	'us_shapefile' - for political boundaries
	'world_shapefile' - for political boundaries
	'NHDPlus' - for stream reach info/IDs

	NOTE: Users may decide to remove large national NHDPlus geodatabase files after regional shapefile creation.
	These items include (~ 25 GB):
		'NHDPlus/NHDPlusNationalData' directory and contents
		'NHDPlus/NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z'
	All other regional shapefiles within the 'NHDPlus' directory should be retained for NWM drought index maps.

	For details on NHDPlus usage:
	http://www.horizon-systems.com/NHDPlusData/NHDPlusV21/Data/NationalData/0Release_Notes_NationalData_Seamless_GeoDatabase.pdf

	bnb2
'''
import os
import requests

### Region definitions. These are used to create filtered and cropped NHDPlus data files.
regions = {
	'ne':{'bbox':[-83.0, 37.0, -66.5, 48.0]},
	'nedews':{'bbox':[-80.2, 40.2, -66.6, 47.7]},
	'ny':{'bbox':[-80.50, 40.40, -71.10, 45.20]},
	'vt':{'bbox':[-74.00, 42.50, -71.20, 45.70]},
	'me':{'bbox':[-72.00, 42.75, -66.35, 48.10]},
	'nh':{'bbox':[-73.10, 42.40, -69.90, 45.60]},
	'ma':{'bbox':[-73.75, 41.20, -69.75, 43.40]},
	'ct':{'bbox':[-74.00, 40.75, -71.25, 42.50]},
	'ri':{'bbox':[-72.50, 41.00, -70.50, 42.50]}
}

### URLs for data to download. Files will be downloaded to directories with key names.
filesToDownload = {
	'us_shapefile':{
		'files':[
			'https://github.com/matplotlib/basemap/raw/master/examples/st99_d00.dbf',
			'https://github.com/matplotlib/basemap/raw/master/examples/st99_d00.shp',
			'https://github.com/matplotlib/basemap/raw/master/examples/st99_d00.shx'
		]
	},
	'world_shapefile':{
		'files':[
			'http://ec.europa.eu/eurostat/cache/GISCO/geodatafiles/CNTR_2014_10M_SH.zip'
		]
	},
	'NHDPlus':{
		'files':[
			'https://edap-ow-data-commons.s3.amazonaws.com/NHDPlusV21/Data/NationalData/NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z'
		]
	}
}

### Download files to local directories, as specified in keys of 'filesToDownload'
for k,v in filesToDownload.items():
	if not os.path.exists(k): res = os.mkdir(k)
	for url in v['files']:
		# download file from url
		print 'downloading '+url
		r = requests.get(url, allow_redirects=True)
		fname = url.split('/')[-1]
		open(k+'/'+fname, 'wb').write(r.content)
		# extract if necessary
		ext = fname.split('.')[-1]
		if ext=='zip':
			print '... extracting '+k+'/'+fname
			cmd = 'unzip -q '+k+'/'+fname+' -d '+k
			res = os.system(cmd)
		if ext=='7z':
			print '... extracting '+k+'/'+fname
			cmd = '7za x '+k+'/'+fname+' -o'+k+'/.'
			res = os.system(cmd)

### regional filter commands
for region in regions.keys():
	print 'creating regional NHDPlus shapefile for '+region
	bbox_string = ' '.join([str(v) for v in regions[region]['bbox']])
	cmd = 'ogr2ogr -f "ESRI Shapefile" -sql "SELECT COMID, TotDASqKm FROM NHDFlowline_Network WHERE TotDASqKm>0.0" -spat '+bbox_string+' ./NHDPlus/NHDFlowline_Network_'+region+'.shp ./NHDPlus/NHDPlusNationalData/NHDPlusV21_National_Seamless_Flattened_Lower48.gdb'
	res = os.system(cmd)

