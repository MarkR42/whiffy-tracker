API_KEY=$(cat api_key.txt)

set -x
POST -c application/json "https://www.googleapis.com/geolocation/v1/geolocate?key=$API_KEY" < example.json 


