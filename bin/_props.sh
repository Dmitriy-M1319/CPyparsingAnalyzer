#!/bin/bash

WINEPREFIX='/home/dimonchik/.prefix32'

WINE="eval WINEPREFIX=$WINEPREFIX wine"

CSC="$WINE 'c:/windows/Microsoft.NET/Framework/v2.0.50727/csc.exe'"
ILASM="$WINE 'c:/windows/Microsoft.NET/Framework/v2.0.50727/ilasm.exe'"
ILDASM="$WINE '"$CD"/.net/mono/ildasm.exe'"

CSC=mcs
ILASM=ilasm
