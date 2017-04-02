function addContourLayer(geojsonUrl, map, layerCollection) {
    console.log('create contour layer for geojson_url', geojsonUrl);

    var replacer = function(key, value) {
        if (value.geometry) {
            var type;
            var rawType = value.type;
            var geometry = value.geometry;

            if (rawType === 1) {
                type = geometry.length === 1 ? 'Point' : 'MultiPoint';
            } else if (rawType === 2) {
                type = geometry.length === 1 ? 'LineString' : 'MultiLineString';
            } else if (rawType === 3) {
                type = geometry.length === 1 ? 'Polygon' : 'MultiPolygon';
            }

            return {
                'type': 'Feature',
                'geometry': {
                    'type': 'MultiLineString',
                    'coordinates': geometry.length == 1 ? geometry : geometry  //  TODO: remove and report as bug in OL example
                },
                'properties': value.tags
            };
        } else {
            return value;
        }
    };

    var tilePixels = new ol.proj.Projection({
        code: 'TILE_PIXELS',
        units: 'tile-pixels'
    });


    return fetch(geojsonUrl).then(function(response) {
        return response.json();
    }).then(function(json) {
        var tileIndex = geojsonvt(json, {
            extent: 4096,
            debug: 1
        });

        var vectorSource = new ol.source.VectorTile({
            format: new ol.format.GeoJSON(),
            tileGrid: ol.tilegrid.createXYZ(),
            tilePixelRatio: 16,
            tileLoadFunction: function(tile) {
                var format = tile.getFormat();
                var tileCoord = tile.getTileCoord();
                var data = tileIndex.getTile(tileCoord[0], tileCoord[1], -tileCoord[2] - 1);

                var features = format.readFeatures(
                    JSON.stringify({
                        type: 'FeatureCollection',
                        features: data ? data.features : []
                    }, replacer));
                    tile.setLoader(function() {
                        tile.setFeatures(features);
                        tile.setProjection(tilePixels);
                    });
                },
            url: 'data:' // arbitrary url, we don't use it in the tileLoadFunction
        });

        function lineStyleFunction(feature, resolution) {
            var strokeWidth = feature.get('stroke-width');
            var zoom = map.getView().getZoom();
            var lineWidth = strokeWidth;
            var value = feature.get('value');
            var color = feature.get('stroke');
            var zoomFactor = 0.7;
            //var is60Line = value % 60 === 0;
            //var is30Line = value % 30 === 0;
            // var is15Line = value % 15 === 0;
            //var is10Line = value % 10 === 0;
            //var is5Line = value % 5 === 0;

            var zoomLevelShow10 = 9;

            if (value % 60 === 0) {
                lineWidth = strokeWidth*2.5;
            }
            else if (value % 30 === 0) {
                lineWidth = strokeWidth*1.5;
            }
            else if (value % 10 === 0) {
                if (zoom <= 8) {
                    color = 'rgba(0,0,0,0)';
                }
                else if (zoom <= 9) {
                    lineWidth = strokeWidth/2.0;
                }
                else {
                    lineWidth = strokeWidth/1.2;
                }
            }
            else if (value % 5 === 0) {
                if (zoom <= 10) {
                    color = 'rgba(0,0,0,0)';
                }
                else {
                    lineWidth = strokeWidth/2.5;
                }
            }

            if (zoom <= 8) {
                lineWidth *= 0.9;
            }

            var lineStyle = new ol.style.Style({
                stroke: new ol.style.Stroke({
                    color: color,
                    width: lineWidth*zoomFactor,
                })
            });
            return lineStyle;
        }

        var vectorLayer = new ol.layer.VectorTile({
            source: vectorSource,
            style: lineStyleFunction,
            updateWhileInteracting: false,
            updateWhileAnimating: false,
            renderMode: 'vector'  // other options stop loading tiles after zooming on large resolutions (OL bug?)
        });

        map.addLayer(vectorLayer);
        layerCollection.push(vectorLayer);
    });
}
