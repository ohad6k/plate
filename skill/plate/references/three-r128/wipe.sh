#!/usr/bin/env bash
# The showcase cut, from two encoded masters (no frame folders on disk):
#   title card "Fable 5.1" on black, the naked film with a black band carrying "Fable 5.1",
#   a line wipes left to right at T0 (film time) over DUR seconds and reveals the pack film,
#   whose band carries "Fable 5.1 + Modpack", at the same frame; a closing card on black.
# Usage: bash wipe.sh [T0] [DUR] [out.mp4] [A=film.mp4] [B=after.mp4]
set -e
cd "$(dirname "$0")"
T0=${1:-4}
DUR=${2:-2}
OUT=${3:-modpack-wipe.mp4}
A=${4:-film.mp4}
B=${5:-after.mp4}
CARD=1.4          # opening card seconds
TAIL=1.6          # closing card seconds
# the label band is added below the picture (1920x1200 canvas), so no HUD is covered
FPS=60
FONT="C\\:/Windows/Fonts/segoeuib.ttf"
OFF=$(python -c "print($CARD+$T0)")
END=$(python -c "print($CARD+$T0+$DUR)")
ffmpeg -y -hide_banner -loglevel error -stats \
  -f lavfi -i "color=c=black:s=1920x1200:r=$FPS:d=$CARD" \
  -i "$A" \
  -ss $T0 -i "$B" \
  -f lavfi -i "color=c=black:s=1920x1200:r=$FPS:d=$TAIL" \
  -filter_complex "\
[0:v]drawtext=fontfile='$FONT':text='Fable 5.1':fontsize=150:fontcolor=white:x=(w-tw)/2:y=(h-th)/2-20,\
drawtext=fontfile='$FONT':text='on the brief as delivered':fontsize=40:fontcolor=white@0.55:x=(w-tw)/2:y=(h-th)/2+110,format=yuv420p,settb=1/60[card];\
[1:v]fps=$FPS,pad=1920:1200:0:0:black,\
drawtext=fontfile='$FONT':text='Fable 5.1':fontsize=64:fontcolor=white:x=48:y=1080+26,format=yuv420p,settb=1/60[a];\
[2:v]fps=$FPS,pad=1920:1200:0:0:black,\
drawtext=fontfile='$FONT':text='Fable 5.1 + Modpack':fontsize=64:fontcolor=white:x=48:y=1080+26,format=yuv420p,settb=1/60[b];\
[card][a]concat=n=2:v=1:a=0,settb=1/60,fps=60[ca];\
[ca][b]xfade=transition=wiperight:duration=$DUR:offset=$OFF[x];\
[x]drawbox=x='(t-$OFF)/$DUR*1920-3':y=0:w=6:h=1200:color=white:t=fill:enable='between(t,$OFF,$END)'[xl];\
[3:v]drawtext=fontfile='$FONT':text='Fable 5.1 + Modpack':fontsize=150:fontcolor=white:x=(w-tw)/2:y=(h-th)/2-20,\
drawtext=fontfile='$FONT':text='same data · same cameras · same 25 seconds':fontsize=40:fontcolor=white@0.55:x=(w-tw)/2:y=(h-th)/2+110,format=yuv420p,settb=1/60[tail];\
[xl][tail]concat=n=2:v=1:a=0[v]" \
  -map "[v]" -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -r $FPS -movflags +faststart "$OUT"
echo "wrote $OUT"
