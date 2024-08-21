'''
	Download shapefiles for political boundaries and stream reach info.

	Two directories will be created, with shapefile contents:
	'us_shapefile' - for political boundaries
	'NHDPlus' - for stream reach info/IDs

	NOTE: National NHDPlus geodatabase files are very large (~25GB), so they are deleted automatically to save on storage space.
	These items include:
		'NHDPlus/NHDPlusNationalData' directory and contents
		'NHDPlus/NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z'
	One cropped set of shapefiles is retained within the 'NHDPlus' directory for NWM drought index maps.

	For details on NHDPlus usage:
	http://www.horizon-systems.com/NHDPlusData/NHDPlusV21/Data/NationalData/0Release_Notes_NationalData_Seamless_GeoDatabase.pdf

	orig bnb2, updated be99
'''
import os
import shutil
import requests

# Return boolean indicating existance of shapefile
def check_for_shapefiles(fnames, local_dir):
	for fname in fnames:
		if not os.path.exists(os.path.join(local_dir, fname)):
			return False
	return True

# Handle downloading the target file and extracting it if necessary
def download_shapefiles(file_group_dict, local_dir):
	source_url = file_group_dict['source']
	for fname in file_group_dict['source_file_names']:
		url = source_url + fname
		r = requests.get(url, allow_redirects=True)
		open(os.path.join(local_dir, fname), 'wb').write(r.content)
		
		# Extract if necessary
		ext = fname.split('.')[-1]
		if ext=='7z':
			cmd = f'7za x {local_dir}/{fname} -o{local_dir}/.'
			os.system(cmd)

# Reduce resolution and geographic bounds of NHDPlus stream geometries, this greatly saves on data storage needs
def crop_and_simplify_nhdplus(config):
	bbox_string = ' '.join([str(v) for v in config.regions['ne']])
	cmd = f'ogr2ogr -simplify 0.001 -f "ESRI Shapefile" -sql "SELECT COMID, TotDASqKm FROM NHDFlowline_Network WHERE TotDASqKm>0.0" -spat {bbox_string} {config.nhdplus_dir}/NHDFlowline_Network.shp {config.nhdplus_dir}/NHDPlusNationalData/NHDPlusV21_National_Seamless_Flattened_Lower48.gdb'
	os.system(cmd)

# Delete any files that are not needed for creating the maps, this greatly saves on data storage needs
def clean_up(file_group_dict, local_dir):
	for fname in file_group_dict['remove_files']:
		fpath = os.path.join(local_dir, fname)
		pieces = fpath.split('.')
		if len(pieces) == 1:
			shutil.rmtree(fpath)
		else:
			os.remove(fpath)

# Handle coordination of getting and altering shapefiles for programs needs
def get_shapefiles(config):
	# URLs for data to download. Files will be downloaded to directories with key names.
	files_to_download = {
		config.us_shp_dir:{
			'source': 'https://github.com/matplotlib/basemap/raw/master/examples/',
			'source_file_names':[ 'st99_d00.dbf', 'st99_d00.shp', 'st99_d00.shx' ],
			'check_file_names':[ 'st99_d00.dbf', 'st99_d00.shp', 'st99_d00.shx' ],
			'remove_files': []
		},
		config.nhdplus_dir:{
			'source': 'https://dmap-data-commons-ow.s3.amazonaws.com/NHDPlusV21/Data/NationalData/',
			'source_file_names':[ 'NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z' ],
			'check_file_names':[ 'NHDFlowline_Network.dbf', 'NHDFlowline_Network.prj', 'NHDFlowline_Network.shp', 'NHDFlowline_Network.shx' ],
			'remove_files': [ 'NHDPlusNationalData', 'NHDPlusV21_NationalData_Seamless_Geodatabase_Lower48_07.7z' ]
		}
	}

	# Loop the dict defined above
	for local_dir, file_group_dict in files_to_download.items():
		# Check if shapefiles already exist
		shp_files_exist = check_for_shapefiles(file_group_dict['check_file_names'], local_dir)

		# If they exist we do not need to get them again
		if not shp_files_exist:
			# Get new shapefiles
			download_shapefiles(file_group_dict, local_dir)

			# If they are NHDPlus stream shapefiles then reduce them
			if local_dir == config.nhdplus_dir:
				crop_and_simplify_nhdplus(config)

			# Delete any unnecessary files
			clean_up(file_group_dict, local_dir)