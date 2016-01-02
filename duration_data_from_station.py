import json
from datetime import datetime, time

from ns_api import Station, NSAPI
from local_settings import USERNAME, APIKEY


def create_trip_data_from_station(station_from):
    nsapi = NSAPI(USERNAME, APIKEY)
    stations = nsapi.get_stations()
    data = {'stations': []}

    timestamp = "30-12-2015 15:50"
    via = ""

    for station in stations:
        if station.country != "NL":
            continue
        # if "Utrecht" not in station.names['long']:
        #     continue

        destination = station.names['long']
        trips = []
        try:
            trips = nsapi.get_trips(timestamp, station_from, via, destination)
        except:
            continue

        if not trips:
            continue

        shortest_trip = trips[0]
        for trip in trips:
            travel_time = datetime.strptime(trip.travel_time_planned, "%H:%M").time()
            trip.travel_time_min = travel_time.hour * 60 + travel_time.minute
            if trip.travel_time_min < shortest_trip.travel_time_min:
                shortest_trip = trip

        print(shortest_trip.departure + ' - ' + shortest_trip.destination)
        data['stations'].append({'name': shortest_trip.destination,
                                 'travel_time_min': shortest_trip.travel_time_min,
                                 'travel_time_planned': shortest_trip.travel_time_planned})

    json_data = json.dumps(data, indent=4, sort_keys=True)
    with open('traveltimes_from_utrecht.json', 'w') as fileout:
        fileout.write(json_data)


if __name__ == "__main__":
    station_from = "Utrecht"
    create_trip_data_from_station(station_from)