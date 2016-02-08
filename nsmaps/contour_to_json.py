import json
import math

from logger import logger


def dotproduct(v1, v2):
    return sum((a * b) for a, b in zip(v1, v2))


def length(v):
    return math.sqrt(dotproduct(v, v))


def angle(v1, v2):
    return math.acos(dotproduct(v1, v2) / (length(v1) * length(v2)))


def contour_to_json(contour, filename, contour_labels, min_angle=2, ndigits=5):
    # min_angle: only create a new line segment if the angle is larger than this angle, to compress output
    collections = contour.collections
    with open(filename, 'w') as fileout:
        total_points = 0
        total_points_original = 0
        collections_json = []
        contour_index = 0
        assert len(contour_labels) == len(collections)
        for collection in collections:
            paths = collection.get_paths()
            color = collection.get_edgecolor()
            paths_json = []
            for path in paths:
                v = path.vertices
                x = []
                y = []
                v1 = v[1] - v[0]
                x.append(round(v[0][0], ndigits))
                y.append(round(v[0][1], ndigits))
                for i in range(1, len(v) - 2):
                    v2 = v[i + 1] - v[i - 1]
                    diff_angle = math.fabs(angle(v1, v2) * 180.0 / math.pi)
                    if diff_angle > min_angle:
                        x.append(round(v[i][0], ndigits))
                        y.append(round(v[i][1], ndigits))
                        v1 = v[i] - v[i - 1]
                x.append(round(v[-1][0], ndigits))
                y.append(round(v[-1][1], ndigits))
                total_points += len(x)
                total_points_original += len(v)

                # x = v[:,0].tolist()
                # y = v[:,1].tolist()
                paths_json.append({u"x": x, u"y": y, u"linecolor": color[0].tolist(), u"label": str(int(contour_labels[contour_index])) + ' min'})
            contour_index += 1

            if paths_json:
                collections_json.append({u"paths": paths_json})
        collections_json_f = {}
        collections_json_f[u"contours"] = collections_json
        fileout.write(json.dumps(collections_json_f, sort_keys=True))  # indent=2)
        logger.info('total points: ' + str(total_points) + ', compression: ' + str(int((1.0 - total_points / total_points_original) * 100)) + '%')