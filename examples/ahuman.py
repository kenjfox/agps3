#!/usr/bin/env python3
# coding=utf-8

"""
ahuman.py is to showcase agps3.py, a Python 2.7-3.5 GPSD interface
Defaults host='127.0.0.1', port=2947, gpsd_protocol='json'

Toggle Lat/Lon form with '0', '1', '2', '3' for RAW, DDD, DMM, DMS

Toggle units with  '0', 'm', 'i', 'n', for 'raw', Metric, Imperial, Nautical

Toggle gpsd protocol with 'j', 'a' for 'json', 'nmea' displays

Quit with 'q' or '^c'

python[X] ahuman.py --help for list of commandline options.
"""

import argparse
import curses
import sys
from datetime import datetime
from math import modf
from time import sleep

sys.path.append("agps3")
from agps3 import GPSDSocket, DataStream

__author__ = "Moe"
__copyright__ = "Copyright 2015-2016  Moe"
__license__ = "MIT"
__version__ = "0.33.2"

CONVERSION = {
    "raw": (1, 1, "m/s", "meters"),
    "metric": (3.6, 1, "kph", "meters"),
    "nautical": (1.9438445, 1, "kts", "meters"),
    "imperial": (2.2369363, 3.2808399, "mph", "feet"),
}


def add_args():
    """Adds commandline arguments and formatted Help"""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-host",
        action="store",
        dest="host",
        default="127.0.0.1",
        help='DEFAULT "127.0.0.1"',
    )
    parser.add_argument(
        "-port",
        action="store",
        dest="port",
        default="2947",
        help="DEFAULT 2947",
        type=int,
    )
    parser.add_argument(
        "-json",
        dest="gpsd_protocol",
        const="json",
        action="store_const",
        default="json",
        help="DEFAULT JSON objects */",
    )
    parser.add_argument(
        "-device",
        dest="devicepath",
        action="store",
        help='alternate devicepath e.g.,"-device /dev/ttyUSB4"',
    )
    # Infrequently used options
    parser.add_argument(
        "-nmea",
        dest="gpsd_protocol",
        const="nmea",
        action="store_const",
        help="*/ output in NMEA */",
    )
    # parser.add_argument('-rare', dest='gpsd_protocol', const='rare', action='store_const', help='*/ output of packets in hex */')
    # parser.add_argument('-raw', dest='gpsd_protocol', const='raw', action='store_const', help='*/ output of raw packets */')
    # parser.add_argument('-scaled', dest='gpsd_protocol', const='scaled', action='store_const', help='*/ scale output to floats */')
    # parser.add_argument('-timing', dest='gpsd_protocol', const='timing', action='store_const', help='*/ timing information */')
    # parser.add_argument('-split24', dest='gpsd_protocol', const='split24', action='store_const', help='*/ split AIS Type 24s */')
    # parser.add_argument('-pps', dest='gpsd_protocol', const='pps', action='store_const', help='*/ enable PPS JSON */')
    parser.add_argument(
        "-v", "--version", action="version", version="Version: {}".format(__version__)
    )
    cli_args = parser.parse_args()
    return cli_args


def satellites_used(feed):
    """Counts number of satellites used in calculation from total visible satellites
    Arguments:
        feed feed=data_stream.satellites
    Returns:
        total_satellites(int):
        used_satellites (int):
    """
    total_satellites = 0
    used_satellites = 0

    if not isinstance(feed, list):
        return 0, 0

    for satellites in feed:
        total_satellites += 1
        if satellites["used"] is True:
            used_satellites += 1
    return total_satellites, used_satellites


def make_time(gps_datetime_str):
    """Makes datetime object from string object"""
    if not "n/a" == gps_datetime_str:
        datetime_string = gps_datetime_str
        datetime_object = datetime.strptime(datetime_string, "%Y-%m-%dT%H:%M:%S")
        return datetime_object


def elapsed_time_from(start_time):
    """calculate time delta from latched time and current time"""
    time_then = make_time(start_time)
    time_now = datetime.utcnow().replace(microsecond=0)
    if time_then is None:
        return
    delta_t = time_now - time_then
    return delta_t


def unit_conversion(thing, units, length=False):
    """converts base data between metric, imperial, or nautical units"""
    if "n/a" == thing:
        return "n/a"
    try:
        thing = round(thing * CONVERSION[units][0 + length], 2)
    except TypeError:
        thing = "fubar"
    return thing, CONVERSION[units][2 + length]


def sexagesimal(sexathang, latlon, form="DDD"):
    """
    Arguments:
        sexathang: (float), -15.560615 (negative = South), -146.241122 (negative = West)  # Apataki Carenage
        latlon: (str) 'lat' | 'lon'
        form: (str), 'DDD'|'DMM'|'DMS', decimal Degrees, decimal Minutes, decimal Seconds
    Returns:
        latitude: e.g., '15°33'38.214"S'
        longitude: e.g., '146°14'28.039"W'
    """
    cardinal = "O"
    if not isinstance(sexathang, float):
        sexathang = "n/a"
        return sexathang

    if latlon == "lon":
        if sexathang > 0.0:
            cardinal = "E"
        if sexathang < 0.0:
            cardinal = "W"

    if latlon == "lat":
        if sexathang > 0.0:
            cardinal = "N"
        if sexathang < 0.0:
            cardinal = "S"

    if form == "RAW":
        sexathang = "{0:4.9f}°".format(
            sexathang
        )  # 4 to allow -100° through -179.999999° to -180°
        return sexathang

    if form == "DDD":
        sexathang = "{0:3.6f}°".format(abs(sexathang))

    if form == "DMM":
        _latlon = abs(sexathang)
        minute_latlon, degree_latlon = modf(_latlon)
        minute_latlon *= 60
        sexathang = "{0}°{1:2.5f}'".format(int(degree_latlon), minute_latlon)

    if form == "DMS":
        _latlon = abs(sexathang)
        minute_latlon, degree_latlon = modf(_latlon)
        second_latlon, minute_latlon = modf(minute_latlon * 60)
        second_latlon *= 60.0
        sexathang = "{0}°{1}'{2:2.3f}\"".format(
            int(degree_latlon), int(minute_latlon), second_latlon
        )

    return sexathang + cardinal


def show_human():
    """Curses terminal with standard outputs"""
    form = "RAW"
    units = "raw"

    data_window = curses.newwin(19, 39, 0, 0)
    sat_window = curses.newwin(14, 39, 0, 40)
    device_window = curses.newwin(6, 39, 13, 40)
    packet_window = curses.newwin(7, 79, 19, 0)

    for new_data in gpsd_socket:
        if new_data:
            data_stream.unpack(new_data)

            screen.nodelay(1)
            key_press = screen.getch()

            if key_press == ord("q"):  # quit
                shut_down()
            elif key_press == ord("a"):  # NMEA
                gpsd_socket.watch(enable=False, gpsd_protocol="json")
                gpsd_socket.watch(gpsd_protocol="nmea")
                show_nmea()
            elif key_press == ord("0"):  # raw
                form = "RAW"
                units = "raw"
                data_window.clear()
            elif key_press == ord("1"):  # DDD
                form = "DDD"
                data_window.clear()
            elif key_press == ord("2"):  # DMM
                form = "DMM"
                data_window.clear()
            elif key_press == ord("3"):  # DMS
                form = "DMS"
                data_window.clear()
            elif key_press == ord("m"):  # Metric
                units = "metric"
                data_window.clear()
            elif key_press == ord("i"):  # Imperial
                units = "imperial"
                data_window.clear()
            elif key_press == ord("n"):  # Nautical
                units = "nautical"
                data_window.clear()
            elif key_press == ord("d"):  # Refresh device listings
                gpsd_socket.send("?DEVICES;")
                device_window.clear()

            data_window.box()
            data_window.addstr(
                0,
                2,
                "AGPS3 Python {}.{}.{} GPSD Interface".format(*sys.version_info),
                curses.A_BOLD,
            )
            data_window.addstr(1, 2, "Time:  {} ".format(data_stream.time))
            data_window.addstr(
                2, 2, "Latitude:  {} ".format(sexagesimal(data_stream.lat, "lat", form))
            )
            data_window.addstr(
                3, 2, "Longitude: {} ".format(sexagesimal(data_stream.lon, "lon", form))
            )
            data_window.addstr(
                4,
                2,
                "Altitude:  {} {}".format(
                    *unit_conversion(data_stream.alt, units, length=True)
                ),
            )
            data_window.addstr(
                5,
                2,
                "Speed:     {} {}".format(*unit_conversion(data_stream.speed, units)),
            )
            data_window.addstr(6, 2, "Heading:   {}° True".format(data_stream.track))
            data_window.addstr(
                7,
                2,
                "Climb:     {} {}".format(
                    *unit_conversion(data_stream.climb, units, length=True)
                ),
            )
            data_window.addstr(8, 2, "Status:     {:<}D  ".format(data_stream.mode))
            data_window.addstr(
                9,
                2,
                "Latitude Err:  +/-{} {}".format(
                    *unit_conversion(data_stream.epx, units, length=True)
                ),
            )
            data_window.addstr(
                10,
                2,
                "Longitude Err: +/-{} {}".format(
                    *unit_conversion(data_stream.epy, units, length=True)
                ),
            )
            data_window.addstr(
                11,
                2,
                "Altitude Err:  +/-{} {}".format(
                    *unit_conversion(data_stream.epv, units, length=True)
                ),
            )
            data_window.addstr(
                12, 2, "Course Err:    +/-{}   ".format(data_stream.epc), curses.A_DIM
            )
            data_window.addstr(
                13,
                2,
                "Speed Err:     +/-{} {}".format(
                    *unit_conversion(data_stream.eps, units)
                ),
                curses.A_DIM,
            )
            data_window.addstr(
                14, 2, "Time Offset:   +/-{}  ".format(data_stream.ept), curses.A_DIM
            )
            data_window.addstr(
                15,
                2,
                "gdop:{}  pdop:{}  tdop:{}".format(
                    data_stream.gdop, data_stream.pdop, data_stream.tdop
                ),
            )
            data_window.addstr(
                16, 2, "ydop:{}  xdop:{} ".format(data_stream.ydop, data_stream.xdop)
            )
            data_window.addstr(
                17, 2, "vdop:{}  hdop:{} ".format(data_stream.vdop, data_stream.hdop)
            )

            sat_window.clear()
            sat_window.box()
            sat_window.addstr(
                0,
                2,
                "Using {0[1]}/{0[0]} satellites (truncated)".format(
                    satellites_used(data_stream.satellites)
                ),
            )
            sat_window.addstr(1, 2, "PRN     Elev   Azimuth   SNR   Used")
            line = 2
            if isinstance(
                data_stream.satellites, list
            ):  # Nested lists of dictionaries are strings before data is present
                for sats in data_stream.satellites[0:10]:
                    sat_window.addstr(
                        line,
                        2,
                        "{PRN:>2}   {el:>6}   {az:>5}   {ss:>5}   {used:}".format(
                            **sats
                        ),
                    )
                    line += 1

            device_window.clear()
            device_window.box()
            if not isinstance(
                data_stream.devices, list
            ):  # Local machines need a 'device' kick start
                gpsd_socket.send("?DEVICES;")  # to have valid data.  I don't know why.

            if isinstance(
                data_stream.devices, list
            ):  # Nested lists of dictionaries are strings before data is present.
                for gizmo in data_stream.devices:
                    start_time, _uicroseconds = gizmo["activated"].split(
                        "."
                    )  # Remove '.000Z'
                    elapsed = elapsed_time_from(start_time)

                    device_window.addstr(
                        1, 2, "Activated: {}".format(gizmo["activated"])
                    )
                    device_window.addstr(
                        2, 2, "Host:{0.host}:{0.port} {1}".format(args, gizmo["path"])
                    )
                    device_window.addstr(
                        3, 2, "Driver:{driver}     BPS:{bps}".format(**gizmo)
                    )
                    device_window.addstr(
                        4,
                        2,
                        "Cycle:{0} Hz {1!s:>14} Elapsed".format(
                            1 / gizmo["cycle"], elapsed
                        ),
                    )

            packet_window.clear()
            # packet_window.border(0)
            packet_window.scrollok(True)
            packet_window.addstr(0, 0, "{}".format(new_data))

            #            sleep(.9)

            data_window.refresh()
            sat_window.refresh()
            device_window.refresh()
            packet_window.refresh()
        else:  # Reduced CPU cycles with the non-blocking socket read, by putting 'sleep' here, rather than hitting
            sleep(
                0.3
            )  # the socket fast and furious with hundreds of empty checks between sleeps.


def show_nmea():
    """NMEA output in curses terminal"""
    data_window = curses.newwin(24, 79, 0, 0)

    for new_data in gpsd_socket:
        if new_data:
            screen.nodelay(1)
            key_press = screen.getch()
            if key_press == ord("q"):
                shut_down()
            elif key_press == ord("j"):  # raw
                gpsd_socket.watch(enable=False, gpsd_protocol="nmea")
                gpsd_socket.watch(gpsd_protocol="json")
                show_human()

            data_window.border(0)
            data_window.addstr(
                0,
                2,
                "AGPS3 Python {}.{}.{} GPSD Interface Showing NMEA protocol".format(
                    *sys.version_info
                ),
                curses.A_BOLD,
            )
            data_window.addstr(2, 2, "{}".format(gpsd_socket.response))
            data_window.refresh()
        else:
            sleep(0.1)


def shut_down():
    """Closes connection and restores terminal"""
    curses.nocbreak()
    curses.echo()
    curses.endwin()
    gpsd_socket.close()
    print("Keyboard interrupt received\nTerminated by user\nGood Bye.\n")
    sys.exit(1)


if __name__ == "__main__":
    args = add_args()
    gpsd_socket = GPSDSocket()
    gpsd_socket.connect(args.host, args.port)
    gpsd_socket.watch(gpsd_protocol=args.gpsd_protocol)
    data_stream = DataStream()

    screen = curses.initscr()
    screen.clear()
    screen.scrollok(True)
    curses.noecho()
    curses.curs_set(0)
    curses.cbreak()

    try:
        if "json" in args.gpsd_protocol:
            show_human()
        if "nmea" in args.gpsd_protocol:
            show_nmea()

    except KeyboardInterrupt:
        shut_down()
    except (OSError, IOError) as error:
        gpsd_socket.close()
        curses.nocbreak()
        curses.echo()
        curses.endwin()
        sys.stderr.write("\rAHUMAN error--> {}".format(error))
        sys.stderr.write(
            "\rahuman connection to gpsd at '{0}' on port '{1}' failed.\n".format(
                args.host, args.port
            )
        )
        sys.exit(1)  # TODO: gpsd existence check and start

#
# Someday a cleaner Python interface will live here
#
# End
