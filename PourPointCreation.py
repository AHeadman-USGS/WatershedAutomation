#-------------------------------------------------------------------------------
# Name:        module1
# Purpose: Creates pour points from Flow Accumulation based on existing WBD
# boundaries.
#
# Author:      aheadman
#
# Created:     11/10/2016
#-------------------------------------------------------------------------------
from __future__ import print_function, absolute_import
import arcpy, os, traceback
from egis import GPMsg, MsgError
from arcpy import env
arcpy.CheckOutExtension("Spatial")
from arcpy.sa import *

def CreatePourPtRaster(Huc12, FlowAcc, FlowLines, workspace, OutFile, OutRaster):
    try:
        env.workspace = workspace
        env.overwriteOutput = True
        Huc12lyr = arcpy.MakeFeatureLayer_management(Huc12, 'huc12lyr')
        LyrLength = arcpy.GetCount_management(Huc12lyr)
        SaveNum = 1
        OutList = []
        for row in arcpy.da.SearchCursor(Huc12, ['TNMID']):
            GPMsg("Creating pourpoint " + str(SaveNum) + " of " + str(LyrLength.getOutput(0)))
            # Creates ad hoc temp files for each HUC input.
            where = "TNMID" + "='" + row[0] + "'"
            arcpy.SelectLayerByAttribute_management(Huc12lyr, 'NEW_SELECTION', where)
            TempHuc12 = workspace+os.sep+'TempHuc12'
            arcpy.CopyFeatures_management(Huc12lyr, TempHuc12)

            # Clips and buffers flowlines to the HUC12
            arcpy.Clip_analysis(FlowLines, TempHuc12, 'TempClipFL')
            TempClipFL = 'TempClipFL'
            TempBuff = 'TempBufferFL'
            arcpy.Buffer_analysis(TempClipFL, TempBuff, "50 Meters",  "FULL", "FLAT", "ALL")
            arcpy.Clip_analysis(TempBuff, TempHuc12, 'TempBuff2')
            arcpy.Delete_management(TempBuff)
            TempBuff = 'TempBuff2'
            TempMask = 'TempMask'

            # Extacts the FlowAcc model relevant to the existing flowlines.
            Mask = ExtractByMask(FlowAcc, TempBuff)
            Mask.save(TempMask)

            #Find the maximum value in the flow accumulation raster, uses this as
            #the pourpoint
            Result = arcpy.GetRasterProperties_management(TempMask, "MAXIMUM")
            ResultOut = float(Result.getOutput(0))
            outRast = 'outRast' + str(SaveNum)
            outRas = Con(Raster(TempMask), 1, "", "Value =" +str(Result))
            outRas.save(outRast)
            SaveNum = SaveNum + 1
            OutList.append(outRast)
            TempList = [TempBuff, TempClipFL, TempHuc12, TempMask]
            for Temp in TempList:
                arcpy.Delete_management(Temp)

        # Creats the actual point files (initially these were polygons, hence the naming
        # scheme, it didn't work).
        GPMsg("Saving output...")
        OutPolys=[]
        SaveNum = 1
        for item in OutList:
            OutPoly = 'OutPoly' + str(SaveNum)
            arcpy.RasterToPoint_conversion(item, OutPoly)
            OutPolys.append(OutPoly)
            SaveNum = SaveNum+1
            arcpy.Delete_management(item)

        PourPointPolygons = OutFile
        for poly in OutPolys:
            if arcpy.Exists(PourPointPolygons):
                arcpy.Append_management(poly, PourPointPolygons, "NO_TEST", "", "")
                arcpy.Delete_management(poly)
            else:
                arcpy.CopyFeatures_management(poly, PourPointPolygons)
                arcpy.Delete_management(poly)

        # Adding an attribution step
        GPMsg("Adding Attribution...")
        PourPoints = OutFile
        arcpy.AddField_management(PourPoints, "Huc12", "TEXT", field_length=14)
        PourPointsLyr = arcpy.MakeFeatureLayer_management(PourPoints, 'PourPoints_lyr')
        for point in arcpy.da.SearchCursor(PourPoints, ['OBJECTID']):
            TempPoint = "TempPoint_"+str(point[0])
            where = "OBJECTID" + "=" + str(point[0])
            arcpy.SelectLayerByAttribute_management(PourPointsLyr, 'NEW_SELECTION', where)
            arcpy.CopyFeatures_management(PourPointsLyr, TempPoint)
            arcpy.SelectLayerByLocation_management(Huc12lyr, "contains", TempPoint)
            cursor = arcpy.da.SearchCursor(Huc12lyr, ['HUC12'])
            for row in cursor:
                HucVal = str(row[0])
                with arcpy.da.UpdateCursor(PourPoints, ['OBJECTID', 'Huc12'], where) as update:
                    for value in update:
                        value[1] = HucVal
                        update.updateRow(value)
            arcpy.Delete_management(TempPoint)



        # Runs SnapPoints to build a snap points raster for the Watershed step.
        GPMsg("Snapping pour points...")
        SnapPoints = SnapPourPoint(PourPointPolygons, FlowAcc, "10", 'OBJECTID')
        SnapPoints.save(OutRaster)

    except MsgError, xmsg:
        GPMsg("e", str(xmsg))


if __name__ == "__main__":
    # ArcGIS Script tool interface
    argv = tuple(arcpy.GetParameterAsText(i)
        for i in range(arcpy.GetArgumentCount()))
    CreatePourPtRaster(*argv)





