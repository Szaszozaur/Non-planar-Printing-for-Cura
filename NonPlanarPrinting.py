
from ..Script import Script
from UM.Application import Application
import math
import re


class NonPlanarPrinting(Script):
    source = ''
    file_object = open(source, 'a' )
    BED_CENTER_X = 0
    BED_CENTER_Y = 0

    gcodeX = 0
    gcodeY = 0
    gcodeZ = 0
    gcodeE = 0
    gcodeF = 0
    lastGcodeX = gcodeX
    lastGcodeY = gcodeY
    lastGcodeZ = gcodeZ
    lastGcodeE = gcodeE
    lastGcodeF = gcodeF
    X = 0
    Y = 0
    Z = 0
    E = 0
    F = 0

    newText = []
    start = 0
    end = 0

    # *****************************************************************************************************
    # Set up paramter input string
    # *****************************************************************************************************

    def getSettingDataString(self):
        return """{
            "name": "Create Non Planar Layers",
            "key": "CreateNonPlanarLayers",
            "metadata": {},
            "version": 2,
            "settings":
            {
                 "wave_amplitude":
                {
                    "label": "Wave amplitude",
                    "description": "[mm] the maximum amplitude of the wavyness",
                    "type": "float",
                    "default_value": "5.0",
                    "minimum_value": "0.5"
                },
                "wave_length":
                {
                    "label": "Wave length",
                    "description": "[mm] the half wave length in xy direction of the waves for wing",
                    "type": "float",
                    "default_value": "20.0",
                    "minimum_value": "0.0"
                },
                "wave_length_2":
                {
                    "label": "Wave length 2",
                    "description": "[mm] the half wave length in xy direction of the waves",
                    "type": "float",
                    "default_value": "20.0",
                    "minimum_value": "0.0"
                },
                "wave_in":
                {
                    "label": "Wave in",
                    "description": "[mm] the z-position where it starts getting wavy, should be somewhere above the first layer",
                    "type": "float",
                    "default_value": "1.0",
                    "minimum_value": "0.4"
                },
                "wave_out":
                {
                    "label": "Wave out",
                    "description": "[mm] the z-position where it starts getting wavy, should be somewhere above the first layer",
                    "type": "float",
                    "default_value": "30.0",
                    "minimum_value": "0.4"
                },
                "wave_ramp":
                {
                    "label": "Wave ramp",
                    "description": "[mm] the length of the transition between not wavy at all and maximum wavyness",
                    "type": "float",
                    "default_value": "5",
                    "minimum_value": "5"
                },
                "wave_max_segment_length":
                {
                    "label": "Wave Max Segment Length",
                    "description": "[mm] max. length of the wave segments, smaller values give a better approximation",
                    "type": "float",
                    "default_value": "0.2",
                    "minimum_value": "0.2"
                },
                "wave_digits":
                {
                    "label": "Wave digits",
                    "description": "[1] accuracy of output g-code",
                    "type": "float",
                    "default_value": "4",
                    "minimum_value": "0.4"
                },
                "wave_function":
                {
                    "label": "Wave function",
                    "description": "can be wave, wing or any function that returns a numeric value.",
                    "type": "str",
                    "default_value": "wave"
                }
            }
        }"""

    def dist3(self, lastGcodeX, lastGcodeY, lastGcodeZ, x, y, z):
        return math.sqrt(math.pow(x - lastGcodeX, 2) + math.pow(y - lastGcodeY, 2) + math.pow(z - lastGcodeZ, 2))

    def dist2(self, lastGcodeX, lastGcodeY, x, y):
        return math.sqrt(math.pow(float(x) - lastGcodeX, 2) + math.pow(float(y) - lastGcodeY, 2))

    def dist1(self, lastGcodeX, x):
        return math.sqrt(math.pow(float(x) - lastGcodeX, 2))

    def digitize(self, num, digits):
        factor = math.pow(10, digits)
        return round((num * factor) / factor, 3)

    def calculate_ramps(self, z):
        # print(self.getSettingValueByKey("wave_in"))
        rampA = max(min((float(z) - float(self.getSettingValueByKey("wave_in"))) / float(self.getSettingValueByKey("wave_ramp")), 1.0),
                    0.0)
        rampB = 1.0 - max(min((z - self.getSettingValueByKey("wave_out") + self.getSettingValueByKey(
            "wave_ramp")) / self.getSettingValueByKey("wave_ramp"), 1.0), 0.0)
        return rampA * rampB

    def calculate_z_displacement(self, x, y, z):
        ramps = self.calculate_ramps(z)
        zOffset = 0.0
        # print(z)
        if self.getSettingValueByKey("wave_function") == "wave":
            zOffset = 0.0 - self.getSettingValueByKey("wave_amplitude") / 2.0 + self.getSettingValueByKey(
                "wave_amplitude") / 4.0 * math.sin(
                x - self.BED_CENTER_X) * 2 * math.pi / self.getSettingValueByKey(
                "wave_length") + self.getSettingValueByKey(
                "wave_amplitude") / 4.0 * math.sin(
                y - self.BED_CENTER_Y) * 2 * math.pi / self.getSettingValueByKey("wave_length")
        elif self.getSettingValueByKey("wave_function") == "wing":
            zOffset = self.getSettingValueByKey("wave_amplitude") / 2.0 + (
                self.getSettingValueByKey("wave_amplitude") * math.sin(((x - self.BED_CENTER_X) * math.sqrt(
                    math.pi) / self.getSettingValueByKey("wave_length") - math.sqrt(
                    math.pow(math.pi / 2, 2))) * 1.0 + 0.5 * math.cos(
                    y - self.BED_CENTER_Y - self.getSettingValueByKey(
                        "wave_length_2") / 4.0) * 2 * math.pi / self.getSettingValueByKey("wave_length_2")))
        zOffset *= ramps
        return zOffset

    def calculate_extrusion_multiplier(self, x, y, z):
        # LAYER_HEIGHT = Application.getInstance().getGlobalContainerStack().getProperty("layer_height", "value")
        LAYER_HEIGHT = 0.2
        ramps = self.calculate_ramps(z)
        this = self.calculate_z_displacement(z, y, z)
        last = self.calculate_z_displacement(x, y, z - LAYER_HEIGHT)
        return 1.0 + (this - last) / LAYER_HEIGHT

    def displace_move(self, thisLine, X, Y, Z, E, F, verbose):
        if float(self.getSettingValueByKey('wave_in')) <= float(self.gcodeZ) <= float(self.getSettingValueByKey('wave_out')):
            x = self.lastGcodeX if self.X == 0 or self.X is None else self.X
            y = self.lastGcodeY if self.Y == 0 or self.Y is None else self.Y
            z = self.lastGcodeZ if self.Z == 0 or self.Z is None else self.Z
            e = self.lastGcodeE if self.E == 0 or self.E is None else self.E
            f = self.lastGcodeF if self.F == 0 or self.F is None else self.F

            distance = self.dist2(self.lastGcodeX, self.lastGcodeY, x, y)

            segments = max(round((distance / float(self.getSettingValueByKey("wave_max_segment_length")))+0.99), 1)

            gcode = " ; displaced move start " + str(segments) + " segments\n"
            # print(segments)
            for i in range(0, segments):

                segmentX = self.lastGcodeX + i + 1 * (float(x) - self.lastGcodeX) / segments
                segmentY = self.lastGcodeY + i + 1 * (float(y) - self.lastGcodeY) / segments
                segmentZ = self.lastGcodeZ + i + 1 * (float(z) - self.lastGcodeZ) / segments

                segmentE = float(self.gcodeE) / segments

                segmentE *= self.calculate_extrusion_multiplier(segmentX, segmentY, segmentZ)

                segmentZ += self.calculate_z_displacement(segmentX, segmentY, segmentZ)
                k=""
                gcode += "G1"
                gcode += " X" + str(self.digitize(segmentX, self.getSettingValueByKey("wave_digits")))
                gcode += " Y" + str(self.digitize(segmentY, self.getSettingValueByKey("wave_digits")))
                gcode += " Z" + str(self.digitize(segmentZ, self.getSettingValueByKey("wave_digits")))
                gcode += " E" + str(self.digitize(segmentE, self.getSettingValueByKey("wave_digits")))
                gcode += "" if F is None else " F" + F
                gcode += " ; segment " + k + " \n"
            gcode += " ; displaced move end\n";
            return gcode
        else:
            return thisLine

    # Functions for additional settings

    def process_start_gcode(self, thisLine):
        # add code here or just return thisLine
        self.start = 1
        return thisLine

    def process_end_gcode(self, thisLine):
        return thisLine

    def process_tool_change(self, thisLine, T, verbose):
        return thisLine

    def process_comment(self, thisLine, C, verbose):
        return thisLine

    def process_layer_change(self, thisLine, z, verbose):
        self.Z = z
        return self.displace_move(thisLine, self.X, self.Y, self.Z, self.E, self.F, verbose)

    def process_retraction_move(self, thisLine, e, f, verbose):
        self.E = e
        self.F = f
        return thisLine

    def process_printing_move(self, thisLine, x, y, z, e, f, verbose):
        self.X = x
        self.Y = y
        self.Z = z
        self.E = e
        self.F = f
        return self.displace_move(thisLine, self.X, self.Y, self.Z, self.E, self.F, verbose)

    def process_touch_off(self, thisLine, X, Y, Z, E, verbose):
        return thisLine+'\n'

    def process_travel_move(self, thisLine, x, y, z, f, verbose):
        self.X = x
        self.Y = y
        self.Z = z
        self.F = f
        return self.displace_move(thisLine, self.X, self.Y, self.Z, self.E, self.F, verbose)

    def process_absolute_extrusion(self, thisLine, verbose):
        return thisLine

    def process_relative_extrusion(self, thisLine, verbose):
        return thisLine

    def process_other(self, thisLine, verbose):
        return thisLine

    # Filtering G_Code
    # Processing routines are called

    def filter_print_gcode(self, thisLine):
        resultComment = re.search('\s*;(.*?)\s*', thisLine)
        resultToolChange = re.search('T(\d)(\s*;\s*([\s\w_-]*)\s*)?', thisLine)
        resultMoves = re.search(
            'G[01](\s+F(-?\d*\.?\d+))?(\s+X(-?\d*\.?\d+))?(\s+Y(-?\d*\.?\d+))?(\s+Z(-?\d*\.?\d+))?(\s+E(-?\d*\.?\d+))?(\s*;\s*([\s\w_-]*)\s*)?',
            thisLine)
        resultG92 = re.search(
            'G92(\s+X(-?\d*\.?\d+))?(\s*Y(-?\d*\.?\d+))?(\s*Z(-?\d*\.?\d+))?(\s*E(-?\d*\.?\d+))?(\s*;\s*([\s\w_-]*)\s*)*',
            thisLine)
        resultAbsoluteExtrusion = re.search('M82(\s*;\s*([\s\w_-]*)\s*)?', thisLine)
        resultRelativeExtrusion = re.search('M83(\s*;\s*([\s\w_-]*)\s*)?', thisLine)
        # print(thisLine)
        if resultComment:
            C = resultComment.group(1)
            verbose = ""
            # print(thisLine)
            return self.process_comment(thisLine, C, verbose)
        elif resultToolChange:
            T = resultToolChange.group(1)
            verbose=""
            return self.process_tool_change(thisLine, T, verbose)
        elif resultMoves:
            self.X = resultMoves.group(4)
            self.Y = resultMoves.group(6)
            self.Z = resultMoves.group(8)
            self.E = resultMoves.group(10)
            self.F = resultMoves.group(2)
            verbose = resultMoves.group(12)

            self.lastGcodeX = self.gcodeX
            self.lastGcodeY = self.gcodeY
            self.lastGcodeZ = self.gcodeZ
            self.lastGcodeE = self.gcodeE
            self.lastGcodeF = self.gcodeF
            self.gcodeX = float(self.gcodeX if self.X == 0 or self.X is None else self.X)
            self.gcodeY = float(self.gcodeY if self.Y == 0 or self.Y is None else self.Y)
            self.gcodeZ = float(self.gcodeZ if self.Z == 0 or self.Z is None else self.Z)
            self.gcodeE = float(self.gcodeE if self.E == 0 or self.E is None else self.E)
            self.gcodeF = float(self.gcodeF if self.F == 0 or self.F is None else self.F)
            if self.E:
                if self.X or self.Y or self.Z:
                    # print('move - printing')
                    return self.process_printing_move(thisLine, self.X, self.Y, self.Z, self.E, self.F, verbose)
                else:
                    return self.process_retraction_move(thisLine, self.E, self.F, verbose)
                    # print('move - retraction')
            else:
                if self.Z and not (self.X or self.Y):
                    # print('layer change')
                    return self.process_layer_change(thisLine, self.Z, self.F, verbose)
                else:
                    # print('travel')
                    return self.process_travel_move(thisLine, self.X, self.Y, self.Z, self.F, verbose)

        elif resultG92:
            self.X = resultG92.group(2)
            self.Y = resultG92.group(4)
            self.Z = resultG92.group(6)
            self.E = resultG92.group(8)
            verbose = resultG92.group(10)
            return self.process_touch_off(thisLine, self.X, self.Y, self.Z, self.E, verbose)
        elif resultAbsoluteExtrusion:
            verbose = resultAbsoluteExtrusion.group(2)
            return self.process_absolute_extrusion(thisLine, verbose)
        elif resultRelativeExtrusion:
            verbose = resultRelativeExtrusion.group(2)
            return self.process_relative_extrusion(thisLine, verbose)
        elif re.match('; end of print', thisLine):
            end = 1
        else:
            verbose = ''
            resultVerbose = re.search('.*(\s*;\s*([\s\w_-]*?)\s*)?', thisLine)
            if resultVerbose:
                verbose = resultVerbose.group(2)
            return self.process_other(thisLine, verbose)

    def filter_parameters(self, thisLine):
        resultNumeric = re.search('\s*;\s*([\w_-]*)\s*=\s*(\d*\.?\d+)\s*', thisLine)
        resultBed = re.search(
            '\s*;\s*bed_shapes*=\s*((\d*)x(\d*))\s*,\s*((\d*)x(\d*))\s*,\s*((\d*)x(\d*))\s*,\s*((\d*)x(\d*))\s*',
            thisLine)
        resultOther = re.search('\s*;\s*([\s\w_-]*?)\s*=\s*(.*)\s*', thisLine)

        if resultNumeric:
            key = resultNumeric.group(1)
            value = float(resultNumeric.group(2)) * 1.0
            if (value != 0 and self.getSettingValueByKey(key) is not None):
                self.setProperty(key, value)
        elif resultBed:
            w = resultBed.group(8)
            h = resultBed.group(9)
            if w is not None:
                self.setProperty("bed_width", float(w) * 1.0)
                self.setProperty("bed_center_x", float(w) / 2.0)
            if h is not None:
                self.setProperty("bed_height", float(h) * 1.0)
                self.setProperty("bed_center_y", float(h) / 2.0)
        elif resultOther:
            key = resultOther.group(1)
            value = resultOther.group(2)
            # self.setProperty(key, float(value))

    def print_parameters(self):
        print("; GCODE POST-PROCESSING PARAMETERS:\n\n")
        # print("; OS: $^O\n\n")
        # print("; Environment Variables:\n")
        # for Setting in self.settings:
        #     print("; "+ Setting+" "+self.getSettingValueByKey(Setting))
        # #     print("; *$_*  =  *$ENV{$_}*\n")
        # print("\n");

    def process_buffer(self, thisLine):
        # print(thisLine)
        if thisLine == "; start of print":
            self.start = 1
        elif thisLine == "; end of print":
            self.end = 1

        if self.start == 0:
            self.newText.append(self.process_start_gcode(thisLine))
            self.file_object.write(self.process_start_gcode(thisLine) + '\n')

        elif self.end == 1:

            self.newText.append(self.process_end_gcode(thisLine))
            self.file_object.write(self.process_end_gcode(thisLine) + '\n')
        else:
            self.newText.append(self.filter_print_gcode(thisLine))
            self.file_object.write(self.filter_print_gcode(thisLine) + '\n')
        # print(self.newText)

    def print_buffer(self, data):
        print(data)

    def execute(self, data):
        if __name__ == '__main__':
            UseModule = getSettingDataSimulator.ScriptSim
        else:
            UseModule = self

        for layer in data:

            lines = layer.split('\n')

            for line in lines:
                self.filter_parameters(line)
                self.process_buffer(line)
                # print(line)
                # self.print_buffer(line)

                # for line in lines:
        # print(self.newText)
        self.file_object.close()
        return self.newText
