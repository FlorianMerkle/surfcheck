from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, session
from sqlalchemy import create_engine, MetaData, Table, sql
from werkzeug.utils import secure_filename
from urllib.request import urlopen
from json import loads
from sqlalchemy.sql import select, and_
from PIL import Image
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
import tzlocal
import imdirect 
import uuid
import os
import time
import pprint
import math
import calendar


UPLOAD_FOLDER = 'static/files/'
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Initialize database
db = create_engine('sqlite:///surfcheck.db', echo = True)
connect = db.connect()
metadata = MetaData()
images = Table('images', metadata, autoload = True, autoload_with = db)
spotlist = Table('spotlist', metadata, autoload = True, autoload_with = db)
users = Table('user', metadata, autoload = True, autoload_with = db)
# Create spot-JSON object for '/'



# FROM FLASK DOC
def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Query DB for spots and convert to JSON
def create_spots_json():
	spots = db.execute(select([spotlist]))				# Get spotlist from DB
	return jsonify([dict(spot) for spot in spots])		# Loop through every dataset and convert to dict before turning into JSON object


def get_tide_data():
	tide = urlopen('http://api.worldweatheronline.com/premium/v1/marine.ashx?key=7c7b779fe7c943bb89c54450181309&format=json&q=-8.65,115.2166&tp=24&fx=yes&tide=yes')
	tide_data=loads(tide.read())
	time_now = time.time() + 28800 + 3600 
	tides = []
	tides.append(tide_data['data']['weather'][0]['tides'][0]['tide_data'][0], tide_data['data']['weather'][0]['tides'][0]['tide_data'][1], tide_data['data']['weather'][0]['tides'][0]['tide_data'][2])
	try:
		tides.append(tide_data['data']['weather'][0]['tides'][0]['tide_data'][3], tide_data['data']['weather'][1]['tides'][0]['tide_data'][0], tide_data['data']['weather'][1]['tides'][0]['tide_data'][1], tide_data['data']['weather'][1]['tides'][0]['tide_data'][2])
	except:
		tides.append(tide_data['data']['weather'][1]['tides'][0]['tide_data'][0], tide_data['data']['weather'][1]['tides'][0]['tide_data'][1], tide_data['data']['weather'][1]['tides'][0]['tide_data'][2], tide_data['data']['weather'][1]['tides'][0]['tide_data'][3])
	for tide in range(len(tides)):
		
		if time_now > time.mktime(time.strptime(tides[tide]['tideDateTime'], '%Y-%m-%d %H:%M')) and time_now < time.mktime(time.strptime(tides[tide + 1]['tideDateTime'], '%Y-%m-%d %H:%M')):
			follTide = tides[tide + 1]
			prevTide = tides[tide]
			break
	if prevTide['tide_type'] == 'HIGH':
		x = ((time_now - calendar.timegm(time.strptime(prevTide['tideDateTime'], '%Y-%m-%d %H:%M'))) / (calendar.timegm(time.strptime(prevTide['tideDateTime'], '%Y-%m-%d %H:%M')) - calendar.timegm(time.strptime(follTide['tideDateTime'], '%Y-%m-%d %H:%M')))) * math.pi
		tideNow = ((math.cos(x) + 1) / 2) *  (float(prevTide['tideHeight_mt']) - float(follTide['tideHeight_mt'])) + float(follTide['tideHeight_mt'])
	else:
		x = math.pi + (((time_now - calendar.timegm(time.strptime(prevTide['tideDateTime'], '%Y-%m-%d %H:%M'))) / (calendar.timegm(time.strptime(prevTide['tideDateTime'], '%Y-%m-%d %H:%M')) - calendar.timegm(time.strptime(follTide['tideDateTime'], '%Y-%m-%d %H:%M')))) * math.pi)
		tideNow = ((math.cos(x) + 1) / 2) *  (float(follTide['tideHeight_mt']) - float(prevTide['tideHeight_mt'])) + float(prevTide['tideHeight_mt'])
	return tideNow

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# MSW delivers directions like this: N == 180
def correct_direction(msw_data):
	print (msw_data)
	if msw_data['swell']['components']["combined"]["direction"]:
		msw_data['swell']['components']["combined"]["direction"] = add_180(msw_data['swell']['components']["combined"]["direction"])
	if msw_data['wind']['direction']:
		msw_data['wind']['direction'] = add_180(msw_data['wind']['direction'])
	if 'primary' in msw_data['swell']['components']:
		msw_data['swell']['components']["primary"]["direction"] = add_180(msw_data['swell']['components']["primary"]["direction"])
	if 'secondary' in msw_data['swell']['components']:
		msw_data['swell']['components']["secondary"]["direction"] = add_180(msw_data['swell']['components']["secondary"]["direction"])
	if 'tertiary' in msw_data['swell']['components']:
		msw_data['swell']['components']["tertiary"]["direction"] = add_180(msw_data['swell']['components']["tertiary"]["direction"])
	return msw_data

def add_180(direction):
	if direction < 180:
		direction += 180
	else:
		direction -= 180
	return direction


def get_compass_direction(direction):
	directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW','N']
	print(direction)
	print(round(direction / 22.5))
	return directions[round(direction / 22.5)]

def get_wave_data(spot_id):
	msw = urlopen('http://magicseaweed.com/api/f2d78ce08b0332094edba1f0737e676f/forecast/?spot_id=935&units=uk&fields=timestamp,localTimestamp,swell.absMinBreakingHeight,swell.absMaxBreakingHeight,swell.components.*,wind.speed,wind.direction,wind.compassDirection')
	msw_data = loads(msw.read())
	
	return msw_data

def correct_orientation(filepath):
	img_to_correct = Image.open(filepath)
	exif_orientation = img_to_correct._getexif().get(274)
	print (exif_orientation)
	if exif_orientation:
		if exif_orientation == 1:
			return True
		elif exif_orientation == 2:
			corrected_image = img_to_correct.transpose(Image.FLIP_LEFT_RIGHT)
			corrected_image.save(filepath)
		elif exif_orientation == 3:
			corrected_image = img_to_correct.rotate(180)
			corrected_image.save(filepath)
		elif exif_orientation == 4:
			corrected_image = img_to_correct.transpose(Image.FLIP_TOP_BOTTOM)
			corrected_image.save(filepath)
		elif exif_orientation == 5:
			corrected_image = img_to_correct.rotate(270, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
			corrected_image.save(filepath)
		elif exif_orientation == 6:
			corrected_image = img_to_correct.rotate(270, expand=True)
			corrected_image.save(filepath)
		elif exif_orientation == 7:
			corrected_image = img_to_correct.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
			corrected_image.save(filepath)
		elif exif_orientation == 8:
			corrected_image = img_to_correct.rotate(90, expand=True)
			corrected_image.save(filepath)
		else:
			return False
		return True
	else:
		return False


def insert_foto(msw_data, filename, spot):	# Into Database
	msw_data=get_current_wave_data()
	time_now = time.time()
	ins = images.insert().values(filename=filename, timestamp=time_now, min_height=msw_data['swell']["absMinBreakingHeight"], 
		max_height=msw_data['swell']["absMaxBreakingHeight"], combined_height=msw_data['swell']['components']["combined"]["height"], 
		combined_period=msw_data['swell']['components']["combined"]["period"], 
		combined_direction=msw_data['swell']['components']["combined"]["direction"], 
		wind_speed=msw_data['wind']['speed'], wind_direction=msw_data['wind']['direction'], tide=get_tide_data(), spot_id = spot, user_id = 1,
		secondary_direction=msw_data.get('secondary', {'not': 'found'}).get('direction', None))# Check secondary direction how to insert when not sure if there is such an object ('key', value if key is not there)
	result = db.execute(ins)
	return True
	

def get_current_wave_data():
	msw_data = get_wave_data(session['selected_spot'][0])
	time_now = time.time()
	for dataset in range(len(msw_data)):
		# Loop through JSON object (list of dicts of dicts) to get the forecasted data for time of upload
		if (abs(time_now - msw_data[dataset]['timestamp']) < 5400):
			current_data = msw_data[dataset]
			current_data=correct_direction(current_data)
	return current_data

def get_best_match(spot, current_data):
	sel = select([images]).where(images.c.spot_id == spot)
	results= db.execute(sel)
	spot_images = [dict(row) for row in results]
	best_match = calculate_scores(current_data, spot_images)
	print(best_match)
	return best_match

def calculate_scores(current_data, archived_data):
	for image in archived_data:
		scores = dict()	
		scores['s_height'] = abs(image['combined_height'] - current_data['swell']['components']["combined"]["height"]) * 0.33 # waveheight coefficient
		scores['s_period'] = abs(image['combined_period'] - current_data['swell']['components']["combined"]["period"])
		# Calculate difference of directions and multiply with coefficient
		if abs(image['combined_direction'] - current_data['swell']['components']["combined"]["direction"]) > 180:
			scores['s_direction'] = abs(max(image['combined_direction'], current_data['swell']['components']["combined"]["direction"])-
				(min(image['combined_direction'], current_data['swell']['components']["combined"]["direction"])+360))*0.3
		else:
			scores['s_direction'] = abs(image['combined_direction'] - current_data['swell']['components']["combined"]["direction"])* 0.3
		# Calculate Wind speed score (no malus below 10kmh difference / for every kmh over 10 0.5p)
		if abs(image['wind_speed'] - current_data['wind']['speed']) < 10:
			scores['w_speed'] = 0
		else:
			scores['w_speed'] = (abs(image['wind_speed'] - current_data['wind']['speed']) - 10) * 0.5
		# Calculate wind direction score (take speed into account)
		if abs(image['wind_direction'] - current_data['wind']['direction']) > 180:
			dir_dif = abs(max(image['wind_direction'], current_data['wind']['direction']) - (min(image['wind_direction'], current_data['wind']['direction']) + 360))
		else:
			dir_dif = abs(image['wind_direction'] - current_data['wind']['direction'])
		scores['w_dir'] = scores['w_speed'] * dir_dif * 0.01
				
		try:
			if best_match[1] > sum(scores.values()):
				best_match = (image, sum(scores.values()))
		except:
			best_match = (image, sum(scores.values()))
			print (best_match[0])
	return best_match[0]



# ----------------ROUTES-------------------------------------------

@app.route('/', methods=['GET','POST'])
def index():
	if request.method =='POST':
		res = db.execute(select([spotlist.c.id, spotlist.c.spot_name]).where(spotlist.c.id==request.form.get('spotID')))
		selected_spot =res.fetchone()
		session['selected_spot'] = (selected_spot['id'],selected_spot['spot_name'])
		if request.form.get('upload'):
			return redirect('/upload')
		elif request.form.get('contribute'):
			return redirect('/check')
		return ("some error message")


	if request.method == 'GET':
		spots = create_spots_json()	# only necessary if dropwdown location selection is planned
		sel = select([images, spotlist.c.spot_name, spotlist.c.utc_offset]).where(images.c.spot_id==spotlist.c.id).order_by(images.c.timestamp.desc()).limit(3)	# select last three images
		res = db.execute(sel)
		recent_imgs = [dict(row) for row in res]
		for recent_img in recent_imgs:
			recent_img['combined_direction'] = get_compass_direction(recent_img['combined_direction'])
			recent_img['wind'] = get_compass_direction(recent_img['wind_direction'])
			recent_img['timestamp'] = datetime.utcfromtimestamp(recent_img['timestamp'] + recent_img['utc_offset']).strftime("%d of %B %I:%M %p")
		return render_template('index.html', spots=spots, recent_imgs=recent_imgs)

'''@app.route('/confirm', methods=['GET','POST'])
def confirm():
	
	rotation = request.form.get('rotation')
	print('dadasdasdf' + rotation)

	return redirect('/check')'''


@app.route('/search')	#works
def search():
	sel = select([spotlist.c.id, spotlist.c.spot_name, spotlist.c.region, spotlist.c.country]).where(spotlist.c.spot_name.like('%'+str(request.args.get('q'))+'%'))
	suggestions = db.execute(sel)
	print('hellooooo--------------------')
	return jsonify([dict(suggestion) for suggestion in suggestions])


# FROM FLASK DOC
@app.route('/upload', methods=['GET', 'POST'])	#works
def upload():
	if request.method == 'POST':
	# check if the post request has the file part
		if 'image' not in request.files:
			print('No file part')
			return render_template('upload.html')
		image = request.files['image']
		if image.filename =='':
		# if user does not select file
			print ('No selected file')
		if image and allowed_file(image.filename):
			unique_filename = secure_filename((str(uuid.uuid1()) + '.' + (image.filename.rsplit('.', 1)[1])))
			filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
			image.save(filepath)
			correct_orientation(filepath)
			msw_data = get_current_wave_data()
			insert_foto(msw_data, unique_filename, session['selected_spot'][0])
			return  redirect('/check')
	else:
		return render_template('upload.html')

@app.route('/check')
def check():
	spot = session['selected_spot']			# (spotid, spotname)
	sel = select([images, spotlist.c.spot_name, spotlist.c.utc_offset]).where(images.c.spot_id==spotlist.c.id==spot).order_by(images.c.timestamp.desc()).limit(3)	# select last three images
	res = db.execute(sel)
	recent_imgs = [dict(row) for row in res]
	for recent_img in recent_imgs:
		recent_img['combined_direction'] = get_compass_direction(recent_img['combined_direction'])
		recent_img['wind'] = get_compass_direction(recent_img['wind_direction'])
		recent_img['timestamp'] = datetime.utcfromtimestamp(recent_img['timestamp'] + recent_img['utc_offset']).strftime("%d of %B %I:%M %p")
	current_data = get_current_wave_data()
	current_data['wind_compass_direction'] = get_compass_direction(current_data['wind']['direction'])
	current_data['swell_compass_direction'] = get_compass_direction(current_data['swell']['components']['combined']['direction'])
	similar_image=get_best_match(spot[0], current_data)
	similar_image['timestamp'] = datetime.utcfromtimestamp(similar_image['timestamp'] + recent_img['utc_offset']).strftime("%d of %B %I:%M %p")
	similar_image['swell_compass_direction'] = get_compass_direction(similar_image['combined_direction'])

	print (similar_image)
	return render_template('check.html', recent_imgs=recent_imgs, spot=spot[1], similar_image=similar_image, current_data = current_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
	session.clear()
	if request.method == 'POST':
		# two form in one page
		sel = select([users]).where(users.c.email==request.form.get('inputEmail'))
		res = db.execute(sel)
		result = ([dict(row) for row in res])
		if len(result) == 0: 
			print(request.form.get("inputPassword"))
			print(request.form.get('inputEmail'))
			return ('wrong email ')
		if (check_password_hash(result[0]["password"], request.form.get("inputPassword")) == False):
			return ('wrong password')
		else:
			session["user_id"] = result[0]["id"]
			return redirect('/')
	else:
		return render_template('login.html')

@app.route('/logout')
def logout():
	session.clear()
	return redirect('/')

@app.route('/register', methods=['GET', 'POST'])
def register():
	if request.method == 'POST':
		if not request.form.get('inputPassword'):
			return redirect('login')
		# two form in one page
		print(request.form.get("inputEmail"))
		print('-------------------------------------------')
		print(request.form.get("inputPassword"))

		sel = select([users]).where(users.c.email==request.form.get('inputEmail'))
		print(request.form.get('inputEmail'))
		res = db.execute(sel)
		result = ([dict(row) for row in res])
		if len(result) != 0:
			print('Email exist already')
			return redirect('/')
		else:
			ins = users.insert().values(email=request.form.get('inputEmail'), password=generate_password_hash(request.form.get('inputPassword')))
			db.execute(ins)
			print('registraion successfull')
			return redirect('/')
	else:
		get_tide_data()
		return render_template('register.html')

if __name__=="__main__":
	app.run(debug=True)

