#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CopperTilt TTY - terminal pinball for Linux (curses, Python stdlib only).

Table: a simplified "Midnight Funfair" (geometry embedded below, taken from
assets/tables/midnight_funfair/geometry.json).

Controls:
  Z / Left arrow       left flippers        M / Right arrow   right flipper
  Space / Down / Enter plunger: hold (or tap to start pulling, tap again to fire)
  X / N / Up           nudge (left / right / up) - too many nudges = TILT
  P pause, Q / Esc quit, Space start a new game
Options:
  --autoplay           the computer plays (demo)
  --frames N           stop after N rendered frames
  --dump FILE          write the last screen as plain text (also .ansi / .json with --dump-ansi/--dump-json)
  --headless           no terminal at all (use with --size WxH and --frames)
  --bell               terminal bell on big awards
  --hold SEC           how long one key press keeps a flipper up (default 0.45)
A terminal reports no key releases, so a flipper stays up for --hold seconds
after a press and as long as key autorepeat keeps coming.
"""
import argparse
import json
import math
import os
import random
import sys
import time

GEOMETRY = json.loads(r'''
{"size":[320,640],"ball_r":7.5,"segments":[[10.0,636.0,10.0,165.0,"wall",0,0],[10.0,165.0,10.37,154.47,
"wall",0,0],[10.37,154.47,11.47,143.98,"wall",0,0],[11.47,143.98,13.3,133.61,"wall",0,0],[13.3,133.61,
15.85,123.38,"wall",0,0],[15.85,123.38,19.11,113.35,"wall",0,0],[19.11,113.35,23.05,103.58,"wall",
0,0],[23.05,103.58,27.67,94.11,"wall",0,0],[27.67,94.11,32.94,84.98,"wall",0,0],[32.94,84.98,38.84,
76.24,"wall",0,0],[38.84,76.24,45.33,67.94,"wall",0,0],[45.33,67.94,52.38,60.11,"wall",0,0],[52.38,
60.11,59.96,52.79,"wall",0,0],[59.96,52.79,68.04,46.01,"wall",0,0],[68.04,46.01,76.56,39.82,"wall",
0,0],[76.56,39.82,85.5,34.23,"wall",0,0],[85.5,34.23,94.81,29.28,"wall",0,0],[94.81,29.28,104.43,
25.0,"wall",0,0],[104.43,25.0,114.34,21.39,"wall",0,0],[114.34,21.39,124.47,18.49,"wall",0,0],[124.47,
18.49,134.78,16.29,"wall",0,0],[134.78,16.29,145.22,14.83,"wall",0,0],[145.22,14.83,155.73,14.09,
"wall",0,0],[155.73,14.09,166.27,14.09,"wall",0,0],[166.27,14.09,176.78,14.83,"wall",0,0],[176.78,
14.83,187.22,16.29,"wall",0,0],[187.22,16.29,197.53,18.49,"wall",0,0],[197.53,18.49,207.66,21.39,
"wall",0,0],[207.66,21.39,217.57,25.0,"wall",0,0],[217.57,25.0,227.19,29.28,"wall",0,0],[227.19,29.28,
236.5,34.23,"wall",0,0],[236.5,34.23,245.44,39.82,"wall",0,0],[245.44,39.82,253.96,46.01,"wall",0,
0],[253.96,46.01,262.04,52.79,"wall",0,0],[262.04,52.79,269.62,60.11,"wall",0,0],[269.62,60.11,276.67,
67.94,"wall",0,0],[276.67,67.94,283.16,76.24,"wall",0,0],[283.16,76.24,289.06,84.98,"wall",0,0],[289.06,
84.98,294.33,94.11,"wall",0,0],[294.33,94.11,298.95,103.58,"wall",0,0],[298.95,103.58,302.89,113.35,
"wall",0,0],[302.89,113.35,306.15,123.38,"wall",0,0],[306.15,123.38,308.7,133.61,"wall",0,0],[308.7,
133.61,310.53,143.98,"wall",0,0],[310.53,143.98,311.63,154.47,"wall",0,0],[311.63,154.47,312.0,165.0,
"wall",0,0],[312.0,165.0,312.0,636.0,"wall",0,0],[290.0,636.0,290.0,182.0,"wall",0,0],[290.0,180.0,
311.0,156.0,"gate",-0.75,-0.66],[290.0,624.0,312.0,624.0,"plunger",0,0],[10.0,334.0,17.0,352.0,"wall",
0,0],[10.0,404.0,34.0,430.0,"wall",0.73,-0.68],[37.0,452.0,37.0,520.0,"wall",0,0],[37.0,520.0,101.35,
574.74,"wall",0,0],[34.4,454.4,27.0,470.0,"wall",0,0],[27.0,470.0,27.0,636.0,"wall",0,0],[58.0,466.0,
58.0,512.0,"rubber",0,0],[58.0,512.0,86.0,534.0,"rubber",0,0],[86.0,534.0,58.0,466.0,"sling0",0,0],
[54.5,460.6,61.5,464.6,"rubber",0,0],[290.0,404.0,266.0,430.0,"wall",-0.73,-0.68],[263.0,452.0,263.0,
520.0,"wall",0,0],[263.0,520.0,198.65,574.74,"wall",0,0],[265.6,454.4,273.0,470.0,"wall",0,0],[273.0,
470.0,273.0,636.0,"wall",0,0],[242.0,466.0,242.0,512.0,"rubber",0,0],[242.0,512.0,214.0,534.0,"rubber",
0,0],[214.0,534.0,242.0,466.0,"sling1",0,0],[245.5,460.6,238.5,464.6,"rubber",0,0],[10.0,396.0,26.0,
386.0,"wall",0.53,0.85],[38.0,300.0,38.0,214.0,"wall",0,0],[264.0,300.0,264.0,214.0,"wall",0,0],[104.0,
52.0,104.0,80.0,"wall",0,0],[136.0,52.0,136.0,80.0,"wall",0,0],[168.0,52.0,168.0,80.0,"wall",0,0],
[200.0,52.0,200.0,80.0,"wall",0,0],[232.0,52.0,232.0,80.0,"wall",0,0],[39.5,212.0,39.5,228.0,"target0",
0,0],[39.5,230.0,39.5,246.0,"target1",0,0],[39.5,248.0,39.5,264.0,"target2",0,0],[39.5,266.0,39.5,
282.0,"target3",0,0],[262.5,212.0,262.5,228.0,"drop0",0,0],[262.5,230.0,262.5,246.0,"drop1",0,0],
[262.5,248.0,262.5,264.0,"drop2",0,0],[262.5,266.0,262.5,282.0,"drop3",0,0],[188.76,409.44,199.91,
401.23,"drop4",0,0],[201.43,400.11,212.57,391.89,"drop5",0,0],[214.09,390.77,225.24,382.56,"drop6",
0,0],[182.0,416.0,232.0,379.0,"wall",0,0],[179.6,414.2,188.76,409.44,"wall",0,0],[236.0,354.0,246.0,
344.0,"wall",0,0],[246.0,344.0,256.0,354.0,"wall",0,0],[60.0,322.0,96.0,314.0,"ramp0",-0.22,-0.98],
[60.0,322.0,56.0,294.0,"wall",0,0],[56.0,294.0,100.0,280.0,"wall",0,0],[100.0,280.0,96.0,314.0,"wall",
0,0],[212.0,314.0,248.0,322.0,"ramp1",0.22,-0.98],[212.0,314.0,208.0,290.0,"wall",0,0],[208.0,290.0,
258.0,270.0,"wall",0,0],[258.0,270.0,248.0,322.0,"wall",0,0],[175.87,305.68,184.13,330.32,"ramp2",
0.95,-0.32],[175.87,305.68,185.35,308.5,"wall",0,0],[185.35,308.5,193.61,327.14,"wall",0,0],[193.61,
327.14,184.13,330.32,"wall",0,0]],"circles":[[290.0,182.0,2.5,"wall","lanepost"],[34.0,430.0,2.5,
"wall","slopepost"],[37.0,452.0,3.5,"rubber","seppost"],[58.0,466.0,3.0,"rubber","slingpost"],[58.0,
512.0,3.0,"rubber","slingpost"],[86.0,534.0,3.0,"rubber","slingpost"],[266.0,430.0,2.5,"wall","slopepost"],
[263.0,452.0,3.5,"rubber","seppost"],[242.0,466.0,3.0,"rubber","slingpost"],[242.0,512.0,3.0,"rubber",
"slingpost"],[214.0,534.0,3.0,"rubber","slingpost"],[150.0,622.0,4.0,"rubber","centerpost"],[38.0,
300.0,3.0,"rubber","post"],[38.0,214.0,2.5,"wall","orbitpost"],[264.0,300.0,3.0,"rubber","post"],
[264.0,214.0,2.5,"wall","orbitpost"],[104.0,52.0,2.5,"wall","lanetop"],[136.0,52.0,2.5,"wall","lanetop"],
[168.0,52.0,2.5,"wall","lanetop"],[200.0,52.0,2.5,"wall","lanetop"],[232.0,52.0,2.5,"wall","lanetop"],
[124.0,122.0,12.0,"bumper","bumper0"],[200.0,122.0,12.0,"bumper","bumper1"],[162.0,160.0,12.0,"bumper",
"bumper2"],[104.0,252.0,13.0,"bumper","bumper3"],[216.0,252.0,13.0,"bumper","bumper4"],[182.0,416.0,
3.0,"rubber","post"],[232.0,379.0,3.0,"rubber","post"],[60.0,322.0,2.5,"wall","mouthpost"],[96.0,
314.0,2.5,"wall","mouthpost"],[212.0,314.0,2.5,"wall","mouthpost"],[248.0,322.0,2.5,"wall","mouthpost"],
[175.87,305.68,2.5,"wall","mouthpost"],[184.13,330.32,2.5,"wall","mouthpost"]],"flippers":[{"side":"L",
"pivot":[96.0,580.0],"len":44.0,"r0":7.0,"r1":3.5,"rest":30.0,"up":-18.0},{"side":"R","pivot":[204.0,
580.0],"len":44.0,"r0":7.0,"r1":3.5,"rest":150.0,"up":198.0},{"side":"L","pivot":[22.0,360.0],"len":34.0,
"r0":6.0,"r1":3.0,"rest":24.0,"up":-30.0}],"lanes":[{"pos":[120.0,66.0],"r":7.0,"letter":"F"},{"pos":[152.0,
66.0],"r":7.0,"letter":"A"},{"pos":[184.0,66.0],"r":7.0,"letter":"I"},{"pos":[216.0,66.0],"r":7.0,
"letter":"R"}],"targets":[{"letter":"R","seg":[39.5,212.0,39.5,228.0],"light":[50.0,220.0]},{"letter":"I",
"seg":[39.5,230.0,39.5,246.0],"light":[50.0,238.0]},{"letter":"D","seg":[39.5,248.0,39.5,264.0],"light":[50.0,
256.0]},{"letter":"E","seg":[39.5,266.0,39.5,282.0],"light":[50.0,274.0]}],"drops":[{"bank":"duck",
"letter":"D","seg":[262.5,212.0,262.5,228.0],"light":[252.0,220.0]},{"bank":"duck","letter":"U","seg":[262.5,
230.0,262.5,246.0],"light":[252.0,238.0]},{"bank":"duck","letter":"C","seg":[262.5,248.0,262.5,264.0],
"light":[252.0,256.0]},{"bank":"duck","letter":"K","seg":[262.5,266.0,262.5,282.0],"light":[252.0,
274.0]},{"bank":"shy","letter":"S","seg":[188.76,409.44,199.91,401.23],"light":[186.33,394.33]},{"bank":"shy",
"letter":"H","seg":[201.43,400.11,212.57,391.89],"light":[199.0,385.0]},{"bank":"shy","letter":"Y",
"seg":[214.09,390.77,225.24,382.56],"light":[211.67,375.67]}],"holes":[{"name":"saucer","pos":[150.0,
304.0],"r":8.0,"kick":[-0.28,0.96],"speed":260.0},{"name":"tunnel","pos":[48.0,304.0],"r":8.0,"subway":"saucer"},
{"name":"haunted","pos":[246.0,362.0],"r":8.0,"subway":"saucer"}],"orbits":[{"name":"left","x":[10.0,
38.0],"y":250.0},{"name":"right","x":[264.0,290.0],"y":250.0}],"stars":[[110.0,208.0],[160.0,202.0],
[210.0,208.0]],"kickback":{"rect":[10.0,572.0,17.0,44.0],"launch":[18.5,584.0],"vy":-835.0},"plunger":{"rest":[301.0,
616.5],"lane":[290.0,182.0,22.0,442.0]},"drain_y":648.0,"slings":[[[58.0,466.0],[58.0,512.0],[86.0,
534.0]],[[242.0,466.0],[242.0,512.0],[214.0,534.0]]],"discs":[{"name":"carousel","pos":[162.0,134.0],
"r":46.0,"omega":1.9,"art":"carousel"}],"spinners":[{"name":"wheelspin","pos":[277.0,300.0],"w":24.0}],
"spinner":{"pos":[24.0,282.0],"w":28.0},"lights":{"lane_F":[[120.0,66.0],"yellow","round"],"lane_A":[[152.0,
66.0],"yellow","round"],"lane_I":[[184.0,66.0],"yellow","round"],"lane_R":[[216.0,66.0],"yellow",
"round"],"ride_R":[[50.0,220.0],"red","round"],"ride_I":[[50.0,238.0],"red","round"],"ride_D":[[50.0,
256.0],"red","round"],"ride_E":[[50.0,274.0],"red","round"],"duck_D":[[252.0,220.0],"orange","round"],
"duck_U":[[252.0,238.0],"orange","round"],"duck_C":[[252.0,256.0],"orange","round"],"duck_K":[[252.0,
274.0],"orange","round"],"shy_S":[[186.33,394.33],"cyan","round"],"shy_H":[[199.0,385.0],"cyan","round"],
"shy_Y":[[211.67,375.67],"cyan","round"],"star0":[[110.0,208.0],"white","star"],"star1":[[160.0,202.0],
"white","star"],"star2":[[210.0,208.0],"white","star"],"mult2":[[114.0,472.0],"orange","round"],"mult3":[[132.0,
472.0],"orange","round"],"mult4":[[150.0,472.0],"orange","round"],"mult5":[[168.0,472.0],"orange",
"round"],"mult6":[[186.0,472.0],"orange","round"],"lorbit_arrow":[[24.0,318.0],"yellow","arrow"],
"lorbit1":[[24.52,332.99],"yellow","round"],"lorbit2":[[24.8,340.99],"yellow","round"],"tunnel_arrow":[[50.0,
336.0],"magenta","arrow"],"tunnel1":[[51.57,350.92],"magenta","round"],"tunnel2":[[52.4,358.87],"magenta",
"round"],"coaster_arrow":[[82.0,348.0],"red","arrow"],"coaster1":[[84.6,362.77],"red","round"],"coaster2":[[85.99,
370.65],"red","round"],"coaster3":[[87.38,378.53],"red","round"],"saucer_arrow":[[144.0,332.0],"white",
"arrow"],"saucer1":[[144.0,347.0],"white","round"],"saucer2":[[144.0,355.0],"white","round"],"helter_arrow":[[174.0,
350.0],"gold","arrow"],"helter1":[[159.9,355.13],"gold","round"],"ghost_arrow":[[226.0,348.0],"green",
"arrow"],"ghost1":[[223.4,362.77],"green","round"],"ghost2":[[222.01,370.65],"green","round"],"haunted_arrow":[[252.0,
388.0],"magenta","arrow"],"haunted1":[[254.09,402.85],"magenta","round"],"rorbit_arrow":[[277.0,318.0],
"yellow","arrow"],"rorbit1":[[276.48,332.99],"yellow","round"],"rorbit2":[[276.2,340.99],"yellow",
"round"],"jackpot":[[150.0,384.0],"white","star"],"lock":[[270.0,410.0],"magenta","round"],"lock1":[[258.0,
434.0],"magenta","round"],"lock2":[[282.0,434.0],"magenta","round"],"super":[[150.0,366.0],"gold",
"round"],"meter0":[[301.0,586.0],"cyan","round"],"meter1":[[301.0,570.0],"green","round"],"meter2":[[301.0,
554.0],"green","round"],"meter3":[[301.0,538.0],"orange","round"],"meter4":[[301.0,522.0],"red","round"],
"kickback":[[18.5,542.0],"green","arrow"],"shoot_again":[[150.0,556.0],"red","round"],"extra_l":[[47.5,
494.0],"green","round"],"extra_r":[[252.5,494.0],"green","round"],"extra_ball":[[150.0,494.0],"orange",
"round"],"spinner":[[24.0,300.0],"cyan","round"],"tower0":[[173.0,250.0],"gold","round"],"tower1":[[169.19,
259.19],"gold","round"],"tower2":[[160.0,263.0],"gold","round"],"tower3":[[150.81,259.19],"gold",
"round"],"tower4":[[147.0,250.0],"gold","round"],"tower5":[[150.81,240.81],"gold","round"],"tower6":[[160.0,
237.0],"gold","round"],"tower7":[[169.19,240.81],"gold","round"]},"ramps":[{"name":"coaster","mouth":[60.0,
322.0,96.0,314.0],"in":[-0.22,-0.98],"path":[[78.0,318.0],[78.37,314.03],[78.93,308.48],[79.5,301.89],
[79.91,294.77],[79.99,288.24],[79.88,282.69],[79.64,276.82],[79.31,270.72],[78.92,264.49],[78.47,
258.22],[78.0,252.0],[77.49,246.11],[76.88,240.15],[76.22,234.14],[75.55,228.1],[74.91,222.05],[74.33,
216.01],[73.84,210.0],[73.25,203.97],[72.59,197.92],[72.0,191.88],[71.59,185.85],[71.47,179.87],[71.78,
173.95],[72.63,167.87],[73.95,161.6],[75.65,155.35],[77.66,149.19],[79.91,143.23],[82.33,137.57],
[84.94,132.07],[87.82,126.43],[90.87,121.06],[94.23,116.03],[98.02,111.41],[102.39,107.27],[107.1,
103.87],[112.23,100.96],[117.82,98.4],[123.74,96.19],[129.83,94.33],[135.96,92.81],[141.91,91.67],
[147.81,90.94],[153.86,90.57],[160.0,90.5],[166.14,90.7],[172.19,91.14],[178.09,91.76],[184.21,92.61],
[190.46,93.72],[196.6,95.1],[202.62,96.78],[208.48,98.78],[214.15,101.13],[219.64,103.85],[224.99,
106.91],[230.18,110.3],[235.19,114.02],[239.99,118.07],[244.54,122.46],[248.57,126.88],[252.32,131.47],
[255.9,136.35],[259.29,141.49],[262.46,146.83],[265.37,152.35],[268.0,158.0],[270.24,163.42],[272.27,
168.89],[274.06,174.5],[275.63,180.32],[276.98,186.45],[278.1,192.99],[279.0,200.0],[279.45,205.23],
[279.7,210.69],[279.81,216.36],[279.79,222.22],[279.69,228.25],[279.53,234.42],[279.35,240.7],[279.18,
247.07],[279.05,253.51],[279.0,260.0],[279.01,265.68],[279.02,271.53],[279.05,277.54],[279.08,283.65],
[279.1,289.83],[279.13,296.04],[279.14,302.24],[279.15,308.4],[279.14,314.48],[279.1,320.44],[279.05,
326.24],[278.97,332.16],[278.92,338.59],[278.9,344.94],[278.89,351.19],[278.86,357.33],[278.78,363.38],
[278.63,369.31],[278.37,375.12],[277.99,380.81],[277.46,386.37],[276.67,392.25],[275.45,398.95],[273.97,
405.54],[272.29,411.96],[270.48,418.16],[268.63,424.07],[266.8,429.64],[265.07,434.81],[263.11,440.6],
[260.27,447.79],[257.44,454.0],[254.9,459.11],[253.53,461.84],[252.96,463.0],[252.5,464.0]],"s":[0.0,
3.98,9.56,16.18,23.31,29.84,35.39,41.27,47.38,53.62,59.91,66.14,72.06,78.05,84.1,90.17,96.26,102.32,
108.36,114.41,120.5,126.57,132.61,138.59,144.52,150.67,157.07,163.55,170.03,176.4,182.56,188.64,194.98,
201.15,207.2,213.18,219.21,225.02,230.92,237.07,243.39,249.76,256.07,262.14,268.07,274.14,280.28,
286.42,292.49,298.42,304.6,310.95,317.25,323.49,329.69,335.83,341.96,348.12,354.32,360.56,366.84,
373.17,379.15,385.07,391.13,397.28,403.5,409.74,415.97,421.84,427.67,433.55,439.59,445.87,452.5,459.57,
464.81,470.28,475.96,481.82,487.85,494.01,500.3,506.67,513.12,519.6,525.28,531.14,537.14,543.25,549.43,
555.64,561.84,568.0,574.08,580.04,585.84,591.77,598.2,604.54,610.79,616.94,622.98,628.92,634.73,640.44,
646.02,651.95,658.76,665.52,672.16,678.62,684.81,690.67,696.12,702.23,709.97,716.79,722.5,725.56,
726.84,727.95],"apex_s":180.53,"down_s":421.84,"color":"red","loop":null},{"name":"ghost","mouth":[212.0,
314.0,248.0,322.0],"in":[0.22,-0.98],"path":[[230.0,318.0],[230.11,313.96],[230.25,308.27],[230.45,
301.59],[230.74,294.56],[231.13,288.15],[231.63,282.33],[232.24,276.23],[232.88,270.01],[233.46,263.85],
[233.9,257.91],[234.23,251.77],[234.59,245.56],[234.84,239.5],[234.8,233.61],[234.3,227.88],[233.15,
221.66],[231.52,215.16],[229.32,208.94],[226.41,203.3],[222.66,198.5],[218.17,194.48],[212.95,191.1],
[206.92,188.3],[200.0,186.0],[194.87,184.78],[189.18,183.81],[183.09,183.07],[176.77,182.54],[170.38,
182.2],[164.07,182.03],[157.99,182.01],[151.81,182.16],[145.52,182.49],[139.25,183.0],[133.11,183.69],
[127.23,184.56],[121.73,185.61],[115.63,187.14],[109.63,189.11],[104.1,191.4],[98.87,194.02],[93.73,
196.95],[88.57,200.2],[83.56,203.78],[78.7,207.67],[74.01,211.88],[69.48,216.42],[65.44,220.88],[61.7,
225.4],[58.09,230.18],[54.6,235.2],[51.24,240.48],[48.0,246.0],[45.18,251.22],[42.41,256.71],[39.75,
262.41],[37.21,268.25],[34.84,274.15],[32.67,280.05],[30.72,285.91],[28.95,291.81],[27.36,297.76],
[25.94,303.76],[24.69,309.81],[23.62,315.91],[22.74,321.95],[22.07,327.87],[21.58,333.85],[21.25,
339.88],[21.05,345.92],[20.97,351.97],[20.98,358.0],[21.06,364.01],[21.19,370.05],[21.41,376.1],[21.76,
382.14],[22.28,388.15],[23.01,394.11],[24.0,400.0],[25.4,406.24],[27.14,412.56],[29.12,418.84],[31.23,
424.97],[33.35,430.82],[35.37,436.29],[37.77,442.57],[40.62,449.24],[43.4,455.31],[45.81,460.36],
[46.47,461.76],[47.5,464.0]],"s":[0.0,4.04,9.73,16.42,23.45,29.87,35.72,41.85,48.09,54.28,60.25,66.39,
72.62,78.68,84.57,90.33,96.65,103.35,109.95,116.3,122.4,128.43,134.66,141.31,148.61,153.88,159.66,
165.79,172.13,178.53,184.84,190.93,197.11,203.4,209.69,215.87,221.82,227.42,233.7,240.02,246.01,251.86,
257.78,263.88,270.04,276.26,282.57,288.98,295.0,300.87,306.85,312.97,319.22,325.63,331.56,337.71,
344.0,350.37,356.73,363.01,369.19,375.35,381.51,387.67,393.85,400.04,406.16,412.11,418.11,424.14,
430.19,436.24,442.27,448.28,454.32,460.37,466.42,472.46,478.47,484.44,490.83,497.39,503.98,510.46,
516.68,522.51,529.24,536.48,543.16,548.76,550.3,552.77],"apex_s":126.42,"down_s":344.0,"color":"green",
"loop":null},{"name":"helter","mouth":[175.87,305.68,184.13,330.32],"in":[0.95,-0.32],"path":[[180.0,
318.0],[184.62,315.55],[190.5,311.63],[194.11,306.56],[196.6,300.35],[198.0,294.0],[197.86,288.4],
[196.72,282.64],[195.8,276.19],[195.15,269.81],[194.47,262.87],[193.83,256.43],[193.18,249.74],[192.57,
243.41],[190.41,237.11],[186.87,231.19],[182.19,226.19],[176.66,222.31],[170.42,219.67],[163.89,218.41],
[157.25,218.52],[150.83,220.02],[144.93,222.77],[139.73,226.71],[135.54,231.56],[132.45,237.15],[130.62,
243.23],[130.09,249.46],[130.88,255.68],[132.9,261.49],[136.08,266.75],[140.26,271.18],[145.63,274.84],
[152.65,277.43],[160.02,278.09],[167.19,276.84],[173.73,273.82],[179.23,269.23],[183.3,263.43],[185.68,
256.88],[186.3,250.02],[185.11,243.27],[182.24,237.14],[177.96,232.05],[172.56,228.27],[166.42,226.05],
[161.64,225.66],[159.42,225.69],[157.87,225.69]],"s":[0.0,5.23,12.31,18.56,25.26,31.77,37.39,43.27,
49.79,56.19,63.17,69.64,76.37,82.72,89.4,96.31,103.17,109.93,116.72,123.38,130.04,136.64,143.16,149.69,
156.11,162.51,168.87,175.13,181.41,187.58,193.73,199.83,206.35,213.84,221.26,228.56,235.78,242.97,
250.07,257.06,263.97,270.83,277.62,284.3,290.89,297.45,302.24,304.46,306.01],"apex_s":31.77,"down_s":69.64,
"color":"gold","loop":null}]}
''')

# ---------------------------------------------------------------- constants
TW, TH = 320.0, 640.0
VIEW_H = 652.0
BALL_R = float(GEOMETRY["ball_r"])
DRAIN_Y = float(GEOMETRY["drain_y"])
GRAV = 390.0
VMAX = 950.0
HZ = 600
DT = 1.0 / HZ
FPS = 30
E_WALL, E_TARGET, E_DEAD = 0.33, 0.25, 0.125
BUMPER_OUT, SLING_OUT = 240.0, 330.0
FL_W0, FL_ACC_UP, FL_ACC_DN = 10.66, 350.0, 248.0
DISC_GRIP = 1.6
CELL = 32.0
BALLS_PER_GAME = 3
BALL_SAVE = 8.0
HOLE_HOLD = 0.9
INLANES = {"inlane_l": (37.0, 58.0), "inlane_r": (242.0, 263.0),
           "outlane_l": (10.0, 27.0), "outlane_r": (273.0, 290.0)}
LANE_LINE_Y = 500.0
RAMP_TITLES = {"coaster": "COASTER", "ghost": "GHOST TRAIN", "helter": "HELTER SKELTER"}


def launch_speed(c):
    c = max(0.0, min(1.0, c))
    if c < 0.3:
        return 640.0 + c / 0.3 * 50.0
    if c < 0.6:
        return 702.0 + (c - 0.3) / 0.3 * 36.0
    return 760.0 + (c - 0.6) / 0.4 * 217.0


def fmt(n):
    return "{:,}".format(int(n))


# ---------------------------------------------------------------- palette
# name -> (xterm-256 index, basic 8-colour index, bold-in-8-colour)
PALETTE = [
    ("cab", 234, 0, False), ("field", 17, 4, False), ("field2", 18, 4, False),
    ("wall", 248, 7, False), ("rubber", 196, 1, True), ("sling", 201, 5, True),
    ("bumper", 226, 3, True), ("bumpring", 202, 1, True), ("flash", 231, 7, True),
    ("flipper", 222, 3, True), ("ball", 231, 7, True), ("ramp", 37, 6, False),
    ("gate", 46, 2, True), ("plunger", 220, 3, True), ("hole", 16, 0, False),
    ("holering", 250, 7, False), ("drop", 208, 3, True), ("target", 203, 1, True),
    ("disc", 54, 5, False),
    ("yellow", 226, 3, True), ("red", 196, 1, True), ("orange", 208, 3, False),
    ("cyan", 51, 6, True), ("magenta", 201, 5, True), ("white", 231, 7, True),
    ("green", 46, 2, True), ("gold", 220, 3, True),
    ("yellow_d", 58, 3, False), ("red_d", 52, 1, False), ("orange_d", 94, 3, False),
    ("cyan_d", 23, 6, False), ("magenta_d", 53, 5, False), ("white_d", 241, 0, True),
    ("green_d", 22, 2, False), ("gold_d", 94, 3, False),
    ("dmd", 214, 3, True), ("dmd_d", 52, 1, False), ("dmd_bg", 232, 0, False),
    ("text", 231, 7, True), ("hud", 250, 7, False), ("hud_bg", 235, 0, False),
    ("warn", 196, 1, True), ("ok", 46, 2, True), ("black", 16, 0, False),
]
C = {p[0]: i for i, p in enumerate(PALETTE)}
XTERM_RGB = []
for _i in range(256):
    if _i < 16:
        _b = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
              (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)]
        XTERM_RGB.append(_b[_i])
    elif _i < 232:
        _j = _i - 16
        _v = [0, 95, 135, 175, 215, 255]
        XTERM_RGB.append((_v[_j // 36], _v[(_j // 6) % 6], _v[_j % 6]))
    else:
        _g = 8 + (_i - 232) * 10
        XTERM_RGB.append((_g, _g, _g))

# ---------------------------------------------------------------- 3x5 font for the DMD
FONT = {
    "0": ["###", "#.#", "#.#", "#.#", "###"], "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###", "..#", "###", "#..", "###"], "3": ["###", "..#", ".##", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"], "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"], "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"], "9": ["###", "#.#", "###", "..#", "###"],
    "A": [".#.", "#.#", "###", "#.#", "#.#"], "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": [".##", "#..", "#..", "#..", ".##"], "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "##.", "#..", "###"], "F": ["###", "#..", "##.", "#..", "#.."],
    "G": [".##", "#..", "#.#", "#.#", ".##"], "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"], "J": ["..#", "..#", "..#", "#.#", ".#."],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"], "L": ["#..", "#..", "#..", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"], "N": ["##.", "#.#", "#.#", "#.#", "#.#"],
    "O": [".#.", "#.#", "#.#", "#.#", ".#."], "P": ["##.", "#.#", "##.", "#..", "#.."],
    "Q": [".#.", "#.#", "#.#", "##.", ".##"], "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": [".##", "#..", ".#.", "..#", "##."], "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"], "V": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "W": ["#.#", "#.#", "###", "###", "#.#"], "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."], "Z": ["###", "..#", ".#.", "#..", "###"],
    " ": ["..", "..", "..", "..", ".."], "!": ["#", "#", "#", ".", "#"],
    ",": ["..", "..", "..", ".#", "#."], ".": [".", ".", ".", ".", "#"],
    "-": ["...", "...", "###", "...", "..."], ":": [".", "#", ".", "#", "."],
    "'": ["#", "#", ".", ".", "."], "?": ["###", "..#", ".#.", "...", ".#."],
    "+": ["...", ".#.", "###", ".#.", "..."], "/": ["..#", "..#", ".#.", "#..", "#.."],
}


def font_width(text):
    return sum(len(FONT.get(ch, FONT["?"])[0]) + 1 for ch in text) - 1 if text else 0


# ---------------------------------------------------------------- physics
class Flipper:
    def __init__(self, d):
        self.side = d["side"]
        self.px, self.py = d["pivot"]
        self.len = float(d["len"])
        self.r0, self.r1 = float(d["r0"]), float(d["r1"])
        self.rest = math.radians(d["rest"])
        self.up = math.radians(d["up"])
        self.a = self.rest
        self.w = 0.0        # signed angular velocity (rad/s)
        self.speed = 0.0

    def update(self, dt, pressed):
        target = self.up if pressed else self.rest
        diff = target - self.a
        if abs(diff) < 1e-6:
            self.w = 0.0
            self.speed = 0.0
            return
        sgn = 1.0 if diff > 0 else -1.0
        moving_same = self.w * sgn > 0
        if pressed:
            self.speed = (self.speed if moving_same else FL_W0) + FL_ACC_UP * dt
        else:
            self.speed = (self.speed if moving_same else 0.0) + FL_ACC_DN * dt
        step = self.speed * dt
        if step >= abs(diff):
            self.a = target
            self.w = 0.0
            self.speed = 0.0
        else:
            self.a += sgn * step
            self.w = sgn * self.speed


class Ball:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.ramp = -1
        self.rs = self.rv = 0.0
        self.held = 0.0
        self.hole = None
        self.cool = 0.0
        self.still = 0.0


class Table:
    """Geometry + solver (a slimmed down port of scripts/table/table.gd)."""

    def __init__(self, game):
        self.game = game
        g = GEOMETRY
        self.segs = [tuple(s) for s in g["segments"]]
        self.circles = [tuple(c) for c in g["circles"]]
        self.flippers = [Flipper(f) for f in g["flippers"]]
        self.lanes = g["lanes"]
        self.stars = g["stars"]
        self.holes = g["holes"]
        self.orbits = g["orbits"]
        self.spinners = [g["spinner"]] + list(g["spinners"])
        self.discs = g["discs"]
        self.kick = g["kickback"]
        self.plunger = g["plunger"]
        self.lights = g["lights"]
        self.targets = g["targets"]
        self.drops_def = g["drops"]
        self.ramps = []
        for r in g["ramps"]:
            m = r["mouth"]
            self.ramps.append(dict(r, a=(m[0], m[1]), b=(m[2], m[3]), len=r["s"][-1]))
        self.drop_down = [False] * len(self.drops_def)
        self.grid = {}
        pad = BALL_R + 4.0
        for i, s in enumerate(self.segs):
            x0, x1 = min(s[0], s[2]) - pad, max(s[0], s[2]) + pad
            y0, y1 = min(s[1], s[3]) - pad, max(s[1], s[3]) + pad
            for cx in range(int(math.floor(x0 / CELL)), int(math.floor(x1 / CELL)) + 1):
                for cy in range(int(math.floor(y0 / CELL)), int(math.floor(y1 / CELL)) + 1):
                    self.grid.setdefault((cx, cy), []).append(i)
        lx, ly, lw, lh = self.plunger["lane"]
        self.lane_rect = (lx, ly, lw, lh)
        self.ball = None
        self.inside = {}

    # -- helpers
    def in_lane(self, b):
        lx, ly, lw, lh = self.lane_rect
        return lx <= b.x <= lx + lw and b.y > ly + 4 and b.ramp < 0

    def ready_to_plunge(self, b):
        return self.in_lane(b) and b.y > self.plunger["rest"][1] - 14 and abs(b.vy) < 60

    def new_ball(self):
        rx, ry = self.plunger["rest"]
        self.ball = Ball(rx, ry)
        return self.ball

    def reset_drops(self, bank=None):
        for i, d in enumerate(self.drops_def):
            if bank is None or d["bank"] == bank:
                self.drop_down[i] = False

    # -- main step
    def step(self, dt, left, right):
        for f in self.flippers:
            f.update(dt, left if f.side == "L" else right)
        b = self.ball
        if b is None:
            return
        if b.cool > 0:
            b.cool -= dt
        if b.held > 0:
            b.held -= dt
            if b.held <= 0:
                self.release_hole(b)
            return
        if b.ramp >= 0:
            self.step_ramp(b, dt)
            return
        ox, oy = b.x, b.y
        b.vy += GRAV * dt
        sp = math.hypot(b.vx, b.vy)
        if sp > VMAX:
            b.vx *= VMAX / sp
            b.vy *= VMAX / sp
        b.x += b.vx * dt
        b.y += b.vy * dt
        for d in self.discs:
            dx, dy = b.x - d["pos"][0], b.y - d["pos"][1]
            if dx * dx + dy * dy < d["r"] * d["r"]:
                ux, uy = -dy * d["omega"], dx * d["omega"]
                k = min(1.0, DISC_GRIP * dt)
                b.vx += (ux - b.vx) * k
                b.vy += (uy - b.vy) * k
        self.collide(b)
        if abs(b.vx) + abs(b.vy) < 4.0:     # break perfect balance on a post top
            b.vx += random.uniform(-3.0, 3.0)
        self.events(b, ox, oy, dt)

    def collide(self, b):
        r = BALL_R
        cell = (int(math.floor(b.x / CELL)), int(math.floor(b.y / CELL)))
        for i in self.grid.get(cell, ()):
            x1, y1, x2, y2, mat, ox, oy = self.segs[i]
            di = -1
            if mat.startswith("drop"):
                di = int(mat[4:])
                if self.drop_down[di]:
                    continue
            abx, aby = x2 - x1, y2 - y1
            l2 = abx * abx + aby * aby
            t = ((b.x - x1) * abx + (b.y - y1) * aby) / l2 if l2 > 0 else 0.0
            t = 0.0 if t < 0 else (1.0 if t > 1 else t)
            cx, cy = x1 + abx * t, y1 + aby * t
            dx, dy = b.x - cx, b.y - cy
            dl = math.hypot(dx, dy)
            if dl >= r or dl < 1e-4:
                continue
            nx, ny = dx / dl, dy / dl
            if mat.startswith("ramp"):
                ri = int(mat[4:])
                rp = self.ramps[ri]
                inx, iny = rp["in"]
                side = (b.x - x1) * inx + (b.y - y1) * iny
                vin = b.vx * inx + b.vy * iny
                if side > 0 or vin <= 0:
                    continue
                if vin > 160 and not self.game.tilted:
                    b.ramp = ri
                    b.rs = 0.0
                    b.rv = math.hypot(b.vx, b.vy) * 0.92
                    continue
                nx, ny = -inx, -iny
            elif ox or oy:
                if (b.x - x1) * ox + (b.y - y1) * oy <= 0:
                    continue
                nx, ny = ox, oy
            b.x, b.y = cx + nx * r, cy + ny * r
            self.respond(b, nx, ny, mat, di)
        for (px, py, cr, mat, cid) in self.circles:
            rr = cr + r
            dx, dy = b.x - px, b.y - py
            d2 = dx * dx + dy * dy
            if d2 >= rr * rr or d2 < 1e-6:
                continue
            dl = math.sqrt(d2)
            nx, ny = dx / dl, dy / dl
            b.x, b.y = px + nx * rr, py + ny * rr
            self.respond(b, nx, ny, mat, -1, cid)
        for f in self.flippers:
            self.flipper_hit(b, f)

    def respond(self, b, nx, ny, mat, di=-1, cid=""):
        vn = b.vx * nx + b.vy * ny
        if vn >= 0:
            return
        vin = -vn
        fr = 0.995 if vin > 30 else 1.0      # impact friction only; resting contact rolls freely
        tx, ty = (b.vx - nx * vn) * fr, (b.vy - ny * vn) * fr
        tilted = self.game.tilted
        if mat == "bumper":
            out = vin * E_DEAD if tilted else max(BUMPER_OUT, vin * 0.8)
            if not tilted:
                self.game.on_bumper(cid)
        elif mat.startswith("sling"):
            if vin > 50 and not tilted:
                out = max(SLING_OUT, vin * 0.7)
                self.game.on_sling(int(mat[5:]))
            else:
                out = min(vin * 0.75, 200 + vin * 0.35)
        elif mat == "rubber":
            out = min(vin * 0.75, 200 + vin * 0.35)
            if vin > 60:
                self.game.add(10)
        elif mat.startswith("target"):
            out = vin * E_TARGET
            self.game.on_target(int(mat[6:]))
        elif mat.startswith("drop"):
            out = vin * E_TARGET
            self.drop_down[di] = True
            self.game.on_drop(di)
        else:
            out = vin * E_WALL if vin >= 25 else 0.0
        b.vx, b.vy = tx + nx * out, ty + ny * out

    def flipper_hit(self, b, f):
        r = BALL_R
        ux, uy = math.cos(f.a), math.sin(f.a)
        qx, qy = b.x - f.px, b.y - f.py
        t = qx * ux + qy * uy
        t = 0.0 if t < 0 else (f.len if t > f.len else t)
        rad = f.r0 + (f.r1 - f.r0) * (t / f.len)
        cx, cy = f.px + ux * t, f.py + uy * t
        dx, dy = b.x - cx, b.y - cy
        dl = math.hypot(dx, dy)
        lim = r + rad
        if dl >= lim or dl < 1e-4:
            return
        nx, ny = dx / dl, dy / dl
        b.x, b.y = cx + nx * lim, cy + ny * lim
        # surface velocity of the contact point
        sx, sy = (cx - f.px) + nx * rad, (cy - f.py) + ny * rad
        vsx, vsy = -sy * f.w, sx * f.w
        rvx, rvy = b.vx - vsx, b.vy - vsy
        vn = rvx * nx + rvy * ny
        if vn >= 0:
            return
        e = 0.39 if abs(f.w) < 0.5 else 0.23
        vtx, vty = rvx - nx * vn, rvy - ny * vn
        fr = 0.985 if vn < -30 else 1.0
        if vn > -30:
            e = 0.0
        b.vx = vsx + vtx * fr - nx * vn * e
        b.vy = vsy + vty * fr - ny * vn * e

    def step_ramp(self, b, dt):
        rp = self.ramps[b.ramp]
        if b.rs < rp["apex_s"]:
            b.rv -= 390.0 * dt
        elif b.rs < rp["down_s"]:
            b.rv -= 20.0 * dt
            if 0 <= b.rv < 40:
                b.rv = 40.0
        else:
            b.rv += 260.0 * dt
        b.rv = min(b.rv, 700.0)
        b.rs += b.rv * dt
        path, ss = rp["path"], rp["s"]
        if b.rs <= 0:
            inx, iny = rp["in"]
            mx = (rp["a"][0] + rp["b"][0]) * 0.5
            my = (rp["a"][1] + rp["b"][1]) * 0.5
            b.ramp = -1
            b.x, b.y = mx - inx * (BALL_R + 2), my - iny * (BALL_R + 2)
            b.vx = -inx * abs(b.rv) + random.uniform(-20, 20)
            b.vy = -iny * abs(b.rv)
            return
        if b.rs >= rp["len"]:
            ri = b.ramp
            b.ramp = -1
            ex, ey = path[-1]
            px, py = path[-3]
            tl = math.hypot(ex - px, ey - py) or 1.0
            v = min(b.rv, 420.0)
            b.x, b.y = ex, ey
            b.vx, b.vy = (ex - px) / tl * v, (ey - py) / tl * v
            self.game.on_ramp(ri)
            return
        lo, hi = 0, len(ss) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ss[mid] <= b.rs:
                lo = mid
            else:
                hi = mid
        seg = ss[hi] - ss[lo] or 1.0
        k = (b.rs - ss[lo]) / seg
        (ax, ay), (bx, by) = path[lo], path[hi]
        b.x, b.y = ax + (bx - ax) * k, ay + (by - ay) * k
        tl = math.hypot(bx - ax, by - ay) or 1.0
        b.vx, b.vy = (bx - ax) / tl * b.rv, (by - ay) / tl * b.rv

    def _enter(self, key, inside):
        was = self.inside.get(key, False)
        self.inside[key] = inside
        return inside and not was

    def events(self, b, ox, oy, dt):
        gm = self.game
        for i, ln in enumerate(self.lanes):
            d = math.hypot(b.x - ln["pos"][0], b.y - ln["pos"][1])
            if self._enter(("lane", i), d < ln["r"]):
                gm.on_lane(i)
        for i, (sx, sy) in enumerate(self.stars):
            if self._enter(("star", i), math.hypot(b.x - sx, b.y - sy) < 7.0):
                gm.on_star(i)
        for o in self.orbits:
            if oy >= o["y"] > b.y and o["x"][0] <= b.x <= o["x"][1]:
                gm.on_orbit(o["name"])
        for sp in self.spinners:
            sy = sp["pos"][1]
            if (oy - sy) * (b.y - sy) < 0 and abs(b.x - sp["pos"][0]) < sp["w"] * 0.5:
                gm.on_spinner(abs(b.vy))
        if oy < LANE_LINE_Y <= b.y:
            for name, (x0, x1) in INLANES.items():
                if x0 <= b.x <= x1:
                    gm.on_inlane(name)
        if b.cool <= 0:
            for h in self.holes:
                hx, hy = h["pos"]
                if math.hypot(b.x - hx, b.y - hy) < h["r"] - 1 and math.hypot(b.vx, b.vy) < 480:
                    b.held = HOLE_HOLD
                    b.hole = h
                    b.x, b.y = hx, hy
                    b.vx = b.vy = 0.0
                    gm.on_hole(h["name"])
                    return
        kx, ky, kw, kh = self.kick["rect"]
        if gm.kickback_lit and kx <= b.x <= kx + kw and ky <= b.y <= ky + kh and b.vy > 0:
            b.x, b.y = self.kick["launch"]
            b.vx, b.vy = 0.0, self.kick["vy"]
            gm.on_kickback()
        sp = math.hypot(b.vx, b.vy)
        if sp < 8 and not self.in_lane(b) and b.y < 560:
            b.still += dt
            if b.still > 3.0:
                b.still = 0.0
                b.vx, b.vy = random.uniform(-120, 120), -380.0
                gm.message("BALL SEARCH", 1.0)
        else:
            b.still = 0.0
        if b.y > DRAIN_Y:
            gm.on_drain()

    def release_hole(self, b):
        h = b.hole
        b.hole = None
        if h.get("subway"):
            dst = next((x for x in self.holes if x["name"] == h["subway"]), None)
            if dst is not None:
                h = dst
        b.x, b.y = h["pos"]
        kx, ky = h.get("kick", (-0.28, 0.96))
        spd = h.get("speed", 260.0)
        b.vx, b.vy = kx * spd, ky * spd
        b.cool = 0.5

    def nudge(self, dx, dy):
        b = self.ball
        if b is None or b.ramp >= 0 or b.held > 0:
            return
        b.vx += dx
        b.vy += dy


# ---------------------------------------------------------------- game rules
class Game:
    def __init__(self, autoplay=False, bell=False, hold=0.45):
        self.autoplay = autoplay
        self.bell = bell
        self.hold = hold
        self.table = Table(self)
        self.t = 0.0
        self.state = "attract"
        self.state_t = 0.0
        self.score = 0
        self.high = self.load_high()
        self.msgs = []
        self.log = []
        self.flash = {}
        self.left_until = self.right_until = 0.0
        self.plunge = None
        self.charge = 0.0
        self.paused = False
        self.quit = False
        self.ai_target = 0.6
        self.match_digit = None
        self.beeps = 0
        self.reset_game_vars()

    # -- persistence
    @staticmethod
    def high_path():
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
        return os.path.join(base, "coppertilt", "tty_highscore")

    def load_high(self):
        try:
            with open(self.high_path()) as fh:
                return int(fh.read().strip() or 0)
        except (OSError, ValueError):
            return 0

    def save_high(self):
        if self.autoplay:
            return
        try:
            os.makedirs(os.path.dirname(self.high_path()), exist_ok=True)
            with open(self.high_path(), "w") as fh:
                fh.write(str(self.high))
        except OSError:
            pass

    # -- flow
    def reset_game_vars(self):
        self.score = 0
        self.ball_no = 1
        self.balls_total = BALLS_PER_GAME
        self.extra_balls = 0
        self.extra_lit = False
        self.match_used = False
        self.ramps_made = 0
        self.ride = [False] * 4
        self.fair = [False] * 4
        self.stars_lit = [False] * 3
        self.mult = 1
        self.jackpot_lit = False
        self.duck_done = self.shy_done = False
        self.reset_ball_vars()

    def reset_ball_vars(self):
        self.bonus = 0
        self.tilted = False
        self.tilt_warn = 0.0
        self.warnings = 0
        self.kickback_lit = True
        self.save_left = BALL_SAVE
        self.save_used = False
        self.launched = False
        self.skill_lane = random.randrange(4)
        self.skill_t = 0.0
        self.combo_t = 0.0
        self.last_ramp = None
        self.table.reset_drops()

    def start_game(self):
        self.reset_game_vars()
        self.state = "play"
        self.table.new_ball()
        self.message("BALL 1", 1.5)
        self.message("PLUNGE!", 1.5)

    def message(self, text, dur=1.6, big=True):
        if self.msgs and self.msgs[-1][0] == text:
            return
        self.msgs.append([text, dur])
        if len(self.msgs) > 4:
            self.msgs.pop(0)
        self.log.append(text)
        self.log = self.log[-6:]

    def ding(self):
        if self.bell:
            self.beeps += 1

    def add(self, pts, bonus=0):
        if self.state != "play" or self.tilted:
            return
        self.score += pts
        self.bonus += bonus

    # -- switch handlers
    def on_bumper(self, cid):
        self.add(300, 50)
        self.flash[cid] = 0.12

    def on_sling(self, i):
        self.add(50)
        self.flash["sling%d" % i] = 0.12

    def on_target(self, i):
        if self.tilted:
            return
        self.flash["target%d" % i] = 0.15
        if not self.ride[i]:
            self.ride[i] = True
            self.add(750, 500)
        else:
            self.add(250)
        if all(self.ride):
            self.ride = [False] * 4
            self.add(10000, 2000)
            self.kickback_lit = True
            self.message("R-I-D-E COMPLETE")
            self.message("KICKBACK LIT", 1.0)

    def on_drop(self, di):
        self.add(1000, 500)
        bank = self.table.drops_def[di]["bank"]
        idx = [i for i, d in enumerate(self.table.drops_def) if d["bank"] == bank]
        if all(self.table.drop_down[i] for i in idx):
            self.add(15000, 3000)
            self.message("D-U-C-K!" if bank == "duck" else "S-H-Y!")
            if bank == "duck":
                self.duck_done = True
            else:
                self.shy_done = True
            self.flash["reset_" + bank] = 1.0
            if self.duck_done and self.shy_done and not self.jackpot_lit:
                self.jackpot_lit = True
                self.message("JACKPOT IS LIT", 1.8)
                self.ding()

    def on_lane(self, i):
        if self.tilted:
            return
        if self.skill_t > 0 and i == self.skill_lane:
            self.skill_t = 0
            self.add(25000)
            self.message("SKILL SHOT")
            self.ding()
        if not self.fair[i]:
            self.fair[i] = True
            self.add(500, 500)
        else:
            self.add(100)
        if all(self.fair):
            self.fair = [False] * 4
            self.add(5000)
            if self.mult < 6:
                self.mult += 1
                self.message("BONUS X%d" % self.mult)

    def on_star(self, i):
        self.stars_lit[i] = True
        self.add(300, 100)
        if all(self.stars_lit):
            self.stars_lit = [False] * 3
            self.add(5000)
            self.message("STARS 5,000", 1.2)

    def on_orbit(self, name):
        self.add(2000, 500)
        self.message("ORBIT 2,000", 0.9)

    def on_spinner(self, vy):
        n = 1 + int(vy / 150)
        self.add(200 * n, 20 * n)

    def on_inlane(self, name):
        if name.startswith("inlane"):
            self.add(1000, 500)
            self.flash["extra_" + name[-1]] = 0.6
            self.combo_t = max(self.combo_t, 2.0)
        else:
            self.add(500)
            if not self.kickback_lit or name.endswith("r"):
                self.message("OUTLANE", 1.0)

    def on_hole(self, name):
        if self.tilted:
            return
        if name == "saucer":
            if self.jackpot_lit:
                pts = 50000 + 1000 * self.ramps_made
                self.add(pts, 10000)
                self.jackpot_lit = False
                self.duck_done = self.shy_done = False
                self.table.reset_drops()
                self.message("JACKPOT " + fmt(pts), 2.5)
                self.ding()
            elif self.extra_lit:
                self.extra_lit = False
                self.extra_balls += 1
                self.message("EXTRA BALL", 2.5)
                self.ding()
            else:
                self.add(3000, 1000)
                self.message("SAUCER 3,000", 1.0)
        else:
            self.add(4000, 1000)
            self.message(("TUNNEL" if name == "tunnel" else "HAUNTED HOUSE") + " 4,000", 1.2)

    def on_kickback(self):
        self.kickback_lit = False
        self.message("KICKBACK", 1.0)

    def on_ramp(self, ri):
        name = self.table.ramps[ri]["name"]
        self.ramps_made += 1
        combo = self.combo_t > 0 and self.last_ramp is not None
        pts = 5000 * (2 if combo else 1)
        self.add(pts, 1000)
        self.combo_t = 4.0
        self.last_ramp = name
        self.message(("COMBO " if combo else "") + RAMP_TITLES.get(name, name.upper()), 1.4)
        if self.ramps_made % 6 == 0 and not self.extra_lit:
            self.extra_lit = True
            self.message("EXTRA BALL LIT", 1.6)

    def on_drain(self):
        tb = self.table
        if self.state != "play":
            tb.ball = None
            return
        if self.launched and not self.save_used and self.save_left > 0 and not self.tilted:
            self.save_used = True
            tb.new_ball()
            self.launched = False
            self.message("BALL SAVED", 2.0)
            return
        tb.ball = None
        self.state = "bonus"
        self.state_t = 0.0
        if self.tilted:
            self.bonus_total = 0
        else:
            self.bonus_total = self.bonus * self.mult
            self.score += self.bonus_total

    def nudge(self, dx, dy):
        if self.state != "play" or self.tilted:
            return
        self.table.nudge(dx, dy)
        self.tilt_warn += 1.0
        if self.tilt_warn > 2.5:
            self.tilted = True
            self.message("TILT", 3.0)
            self.ding()
        elif self.tilt_warn > 1.5:
            self.message("DANGER", 1.0)

    # -- input
    def key(self, k, now):
        if k in ("q", "Q", "ESC"):
            self.quit = True
        elif k in ("p", "P"):
            self.paused = not self.paused
        elif self.paused:
            return
        elif k == "LEFT":
            self.left_until = max(self.left_until, now + (0.12 if self.left_until > now else self.hold))
            self.on_flip()
        elif k == "RIGHT":
            self.right_until = max(self.right_until, now + (0.12 if self.right_until > now else self.hold))
            self.on_flip()
        elif k == "PLUNGE":
            if self.state in ("attract", "over"):
                self.start_game()
                return
            if self.plunge is None:
                self.plunge = {"t0": now, "last": now, "rep": False}
                self.charge = 0.0
            else:
                gap = now - self.plunge["last"]
                if gap < 0.7 or self.plunge["rep"]:
                    self.plunge["rep"] = True
                    self.plunge["last"] = now
                else:
                    self.fire()
        elif k == "NUDGE_L":
            self.nudge(-70, -30)
        elif k == "NUDGE_R":
            self.nudge(70, -30)
        elif k == "NUDGE_U":
            self.nudge(0, -90)

    def on_flip(self):
        # lane change: flipper buttons rotate the lit F-A-I-R lanes
        if self.state == "play" and not self.tilted:
            b = self.table.ball
            if b is not None and b.y < 420:
                return
            if self.last_flip_t is None or self.t - self.last_flip_t > 0.25:
                self.fair = self.fair[-1:] + self.fair[:-1] if self.left_until >= self.right_until else self.fair[1:] + self.fair[:1]
            self.last_flip_t = self.t

    last_flip_t = None

    def fire(self):
        tb = self.table
        b = tb.ball
        if b is not None and self.state == "play" and tb.ready_to_plunge(b):
            b.vy = -launch_speed(self.charge)
            b.vx = 0.0
            if not self.launched:
                self.launched = True
                self.skill_t = 4.0
        self.plunge = None
        self.charge = 0.0

    # -- autoplay brain
    def ai(self, now):
        tb = self.table
        if self.state in ("attract", "over") and self.state_t > 1.5:
            self.start_game()
            return
        b = tb.ball
        if b is None or self.state != "play":
            return
        if tb.ready_to_plunge(b) and self.plunge is None and b.held <= 0:
            self.plunge = {"t0": now, "last": now, "rep": True, "ai": True}
            self.charge = 0.0
            self.ai_target = random.uniform(0.35, 0.95)
        if self.plunge is not None and self.plunge.get("ai"):
            self.plunge["last"] = now
            if self.charge >= self.ai_target:
                self.fire()
        if b.ramp >= 0 or b.held > 0:
            return
        slow = math.hypot(b.vx, b.vy) < 40
        self.ai_cradle = (getattr(self, "ai_cradle", 0.0) + 1.0 / FPS) if slow else 0.0
        if self.ai_cradle > 0.7:          # let a cradled ball roll off, then flip it
            if self.ai_cradle > 1.0:
                self.ai_cradle = 0.0
            return
        for f in tb.flippers:
            fx, fy = f.px, f.py
            near = math.hypot(b.x - fx, b.y - fy) < f.len + 14
            ahead = (b.x >= fx - 6) if f.side == "L" else (b.x <= fx + 6)
            if f.len < 40:                 # upper flipper: only swat a moving ball out on the blade
                ahead = b.x > fx + 8 and not slow
            if near and ahead and b.vy > -40 and b.y < fy + 6:
                if f.side == "L":
                    self.left_until = now + 0.18
                else:
                    self.right_until = now + 0.18

    # -- update
    def update(self, dt, now):
        if self.paused:
            return
        self.t += dt
        self.state_t += dt
        if self.autoplay:
            self.ai(now)
        for k in list(self.flash):
            self.flash[k] -= dt
            if self.flash[k] <= 0:
                del self.flash[k]
                if k.startswith("reset_"):
                    self.table.reset_drops(k[6:])
        if self.msgs:
            self.msgs[0][1] -= dt
            if self.msgs[0][1] <= 0:
                self.msgs.pop(0)
        if self.plunge is not None:
            self.charge = min(1.0, self.charge + dt)
            if self.plunge["rep"] and not self.plunge.get("ai") and now - self.plunge["last"] > 0.14:
                self.fire()
        tb = self.table
        if self.state == "play":
            self.tilt_warn = max(0.0, self.tilt_warn - dt / 3.0) if not self.tilted else self.tilt_warn
            if self.skill_t > 0:
                self.skill_t -= dt
            if self.combo_t > 0:
                self.combo_t -= dt
            b = tb.ball
            if self.launched and b is not None and not tb.in_lane(b) and self.save_left > 0:
                self.save_left -= dt
        left = now < self.left_until and not self.tilted
        right = now < self.right_until and not self.tilted
        steps = int(round(dt * HZ))
        for _ in range(max(1, steps)):
            tb.step(DT, left, right)
        if self.state == "bonus":
            if self.state_t > 2.2:
                self.end_ball()
        elif self.state == "match":
            if self.state_t > 3.0:
                if self.match_hit:
                    self.balls_total += 1
                    self.ball_no += 1
                    self.state = "play"
                    self.reset_ball_vars()
                    tb.new_ball()
                    self.message("MATCH! EXTRA BALL", 2.0)
                else:
                    self.state = "over"
                    self.state_t = 0.0
                    if self.score > self.high:
                        self.high = self.score
                        self.save_high()
                        self.message("NEW HIGH SCORE", 3.0)
                    self.message("GAME OVER", 3.2)

    def end_ball(self):
        tb = self.table
        if self.extra_balls > 0:
            self.extra_balls -= 1
            self.reset_ball_vars()
            tb.new_ball()
            self.state = "play"
            self.message("SHOOT AGAIN", 2.0)
            return
        if self.ball_no < self.balls_total:
            self.ball_no += 1
            self.reset_ball_vars()
            tb.new_ball()
            self.state = "play"
            self.message("BALL %d" % self.ball_no, 1.5)
            return
        self.state_t = 0.0
        if self.match_used:
            self.state = "match"
            self.match_hit = False
            self.state_t = 3.0
            self.match_digit = None
            return
        self.match_used = True
        self.state = "match"
        self.match_digit = random.randrange(10)
        self.match_hit = (self.score // 10) % 10 == self.match_digit
        if self.match_hit:
            self.ding()

    def light_on(self, name):
        t = self.t
        blink = int(t * 4) % 2 == 0
        fast = int(t * 8) % 2 == 0
        if name.startswith("lane_"):
            i = "FAIR".index(name[5])
            if self.skill_t > 0 and i == self.skill_lane:
                return fast
            return self.fair[i]
        if name.startswith("ride_"):
            return self.ride["RIDE".index(name[5])]
        if name.startswith("duck_") or name.startswith("shy_"):
            bank, letter = name.split("_")
            for i, d in enumerate(self.table.drops_def):
                if d["bank"] == bank and d["letter"] == letter:
                    return self.table.drop_down[i]
        if name.startswith("star"):
            return self.stars_lit[int(name[4:])]
        if name.startswith("mult"):
            return self.mult >= int(name[4:])
        if name == "kickback":
            return self.kickback_lit
        if name == "shoot_again":
            return (self.save_left > 0 and not self.save_used and blink) or self.extra_balls > 0
        if name == "extra_ball":
            return self.extra_lit and blink
        if name in ("extra_l", "extra_r"):
            return ("extra_" + name[-1]) in self.flash
        if name in ("jackpot", "super") or name.startswith("saucer"):
            return self.jackpot_lit and blink
        for rn in ("coaster", "ghost", "helter"):
            if name.startswith(rn):
                return (fast if self.combo_t > 0 else blink) if self.state == "play" else False
        if name.startswith("meter"):
            return self.plunge is not None and self.charge >= int(name[5:]) * 0.2
        if name.startswith("tower"):
            return int(t * 6) % 8 == int(name[5:])
        return False


# ---------------------------------------------------------------- renderer
class Renderer:
    def __init__(self):
        self.cols = self.rows = 0
        self.static = None

    def layout(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.dmd_rows = 4
        side = 26 if cols >= 100 else 24
        avail_c = cols - side - 2
        avail_r = rows - self.dmd_rows
        # zoom so the table is at most ~70 columns wide; scroll vertically when it does not fit
        s = max(TW / min(avail_c, 70), 220.0 / (2.0 * avail_r))
        self.s = s
        self.pw = int(math.ceil(TW / s))
        self.ph = int(math.ceil(VIEW_H / s))
        self.tx = max(0, (cols - side - self.pw) // 2)
        self.side_x = self.tx + self.pw + 2
        self.side_w = cols - self.side_x
        self.view_rows = avail_r
        self.view_ph = avail_r * 2
        self.scroll = self.ph > self.view_ph
        self.cam = float(max(0, self.ph - self.view_ph))
        self.build_static()

    # -- raster helpers (pixel space)
    def put(self, buf, x, y, c, y0=0):
        x, y = int(x), int(y) - y0
        if 0 <= x < self.pw and 0 <= y < len(buf):
            buf[y][x] = c

    def line(self, buf, x1, y1, x2, y2, c, y0=0, thick=0.0):
        s = self.s
        ax, ay, bx, by = x1 / s, y1 / s, x2 / s, y2 / s
        n = int(max(abs(bx - ax), abs(by - ay)) * 2) + 1
        for i in range(n + 1):
            t = i / n
            x, y = ax + (bx - ax) * t, ay + (by - ay) * t
            self.put(buf, x, y, c, y0)
            if thick > 0:
                self.disk(buf, x * s, y * s, thick, c, y0)

    def disk(self, buf, cx, cy, r, c, y0=0, ring=None):
        s = self.s
        px, py, pr = cx / s, cy / s, max(r / s, 0.5)
        for y in range(int(py - pr - 1), int(py + pr + 2)):
            for x in range(int(px - pr - 1), int(px + pr + 2)):
                d = math.hypot(x + 0.5 - px, y + 0.5 - py)
                if d <= pr:
                    self.put(buf, x, y, ring if (ring is not None and d > pr - 1.0) else c, y0)
        self.put(buf, px, py, c, y0)

    def build_static(self):
        pw, ph = self.pw, self.ph
        cab, field = C["cab"], C["field"]
        mask = [bytearray(pw) for _ in range(ph)]
        tb = GEOMETRY
        for sg in tb["segments"]:
            if sg[4].startswith("ramp") or sg[4] == "gate":
                continue
            self.line(mask, sg[0], sg[1], sg[2], sg[3], 1)
        self.line(mask, 0, 638, 320, 638, 1)
        buf = [bytearray([cab]) * pw for _ in range(ph)]
        sx, sy = int(150 / self.s), int(400 / self.s)
        stack = [(sx, sy)]
        while stack:
            x, y = stack.pop()
            if 0 <= x < pw and 0 <= y < ph and not mask[y][x] and buf[y][x] == cab:
                buf[y][x] = field
                stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
        # the drain gap under the flippers
        for y in range(int(630 / self.s), ph):
            for x in range(int(10 / self.s), int(290 / self.s) + 1):
                if buf[y][x] == cab and not mask[y][x]:
                    buf[y][x] = C["black"]
        for d in tb["discs"]:
            self.disk(buf, d["pos"][0], d["pos"][1], d["r"], C["disc"], ring=C["magenta_d"])
        for r in tb["ramps"]:
            p = r["path"]
            for i in range(len(p) - 1):
                self.line(buf, p[i][0], p[i][1], p[i + 1][0], p[i + 1][1], C["ramp"])
        for h in tb["holes"]:
            self.disk(buf, h["pos"][0], h["pos"][1], h["r"] + 1.5, C["hole"], ring=C["holering"])
        for sg in tb["segments"]:
            m = sg[4]
            if m.startswith("drop") or m.startswith("target") or m.startswith("ramp"):
                continue
            col = {"rubber": "rubber", "gate": "gate", "plunger": "plunger"}.get(m, "sling" if m.startswith("sling") else "wall")
            self.line(buf, sg[0], sg[1], sg[2], sg[3], C[col])
        for (x, y, r, m, cid) in tb["circles"]:
            if m == "bumper":
                self.disk(buf, x, y, r, C["bumper"], ring=C["bumpring"])
            else:
                self.disk(buf, x, y, r, C["rubber"] if m == "rubber" else C["wall"])
        self.static = buf

    # -- frame
    def frame(self, game):
        cols, rows = self.cols, self.rows
        blank = (" ", C["hud"], C["black"], False)
        cells = [[blank] * cols for _ in range(rows)]
        if cols < 80 or rows < 24:
            msg = "Terminal %dx%d - need at least 80x24" % (cols, rows)
            r = rows // 2
            for i, ch in enumerate(msg[:cols]):
                cells[r][i] = (ch, C["warn"], C["black"], True)
            return cells
        self.draw_dmd(cells, game)
        self.draw_table(cells, game)
        self.draw_side(cells, game)
        if game.paused:
            self.text(cells, self.dmd_rows + self.view_rows // 2, self.tx + self.pw // 2 - 4, " PAUSED ", C["black"], C["yellow"], True)
        return cells

    def text(self, cells, r, c, s, fg, bg, bold=False):
        if not 0 <= r < len(cells):
            return
        row = cells[r]
        for i, ch in enumerate(s):
            if 0 <= c + i < len(row):
                row[c + i] = (ch, fg, bg, bold)

    def dmd_text(self, game):
        if game.state == "bonus":
            return ("BONUS " + fmt(game.bonus_total)) if not game.tilted else "TILT"
        if game.state == "match":
            if game.match_digit is None:
                return fmt(game.score)
            if game.state_t < 1.8:
                return "MATCH %d0" % int(game.t * 12 % 10)
            return ("MATCH %d0" % game.match_digit) + ("!" if game.match_hit else "")
        if game.msgs:
            return game.msgs[0][0]
        if game.state == "attract":
            return "PRESS SPACE" if int(game.t) % 4 < 2 else "COPPERTILT"
        if game.state == "over":
            return "GAME OVER" if int(game.t) % 4 < 2 else fmt(game.score)
        return fmt(game.score)

    def draw_dmd(self, cells, game):
        cols = self.cols
        on, off, bg = C["dmd"], C["dmd_d"], C["dmd_bg"]
        txt = self.dmd_text(game)
        if font_width(txt) > cols - 2:
            txt = fmt(game.score) if font_width(fmt(game.score)) <= cols - 2 else txt[: (cols - 2) // 4]
        w = font_width(txt)
        px = [[False] * cols for _ in range(6)]
        x0 = max(0, (cols - w) // 2)
        x = x0
        for ch in txt:
            gl = FONT.get(ch, FONT["?"])
            for gy, line in enumerate(gl):
                for gx, v in enumerate(line):
                    if v == "#" and 0 <= x + gx < cols:
                        px[gy][x + gx] = True
            x += len(gl[0]) + 1
        for r in range(3):
            for c in range(cols):
                top, bot = px[2 * r][c], px[2 * r + 1][c]
                if top and bot:
                    cells[r][c] = ("█", on, bg, True)
                elif top:
                    cells[r][c] = ("▀", on, bg, True)
                elif bot:
                    cells[r][c] = ("▄", on, bg, True)
                else:
                    cells[r][c] = ("·" if (c % 2 == 0) else " ", off, bg, False)
        # status line
        st = " BALL %d/%d " % (min(game.ball_no, game.balls_total), game.balls_total)
        if game.state in ("attract", "over"):
            st = " GAME OVER " if game.state == "over" else " INSERT COIN: SPACE "
        row = [(" ", C["text"], C["hud_bg"], False)] * cols
        cells[3] = row
        self.text(cells, 3, 0, st, C["black"], C["dmd"], True)
        c = len(st) + 1
        part = "SCORE %s" % fmt(game.score)
        self.text(cells, 3, c, part, C["text"], C["hud_bg"], True)
        c += len(part) + 2
        part = "BONUS X%d" % game.mult
        self.text(cells, 3, c, part, C["orange"], C["hud_bg"], True)
        c += len(part) + 2
        if game.tilted:
            self.text(cells, 3, c, " TILT ", C["text"], C["warn"], True)
            c += 8
        else:
            self.text(cells, 3, c, "TILT", C["hud"], C["hud_bg"], False)
            for i in range(3):
                lit = game.tilt_warn > i + 0.5
                self.text(cells, 3, c + 5 + i, "●" if lit else "○", C["warn"] if lit else C["hud"], C["hud_bg"], lit)
            c += 10
        hs = "HIGH %s" % fmt(max(game.high, game.score))
        if c + len(hs) < cols:
            self.text(cells, 3, cols - len(hs) - 1, hs, C["gold"], C["hud_bg"], True)

    def draw_table(self, cells, game):
        tb = game.table
        s = self.s
        b = tb.ball
        # camera
        if self.scroll:
            if b is not None:
                target = b.y / s - self.view_ph * 0.55
            else:
                target = self.ph - self.view_ph
            target = max(0.0, min(float(self.ph - self.view_ph), target))
            self.cam += (target - self.cam) * 0.35
            if abs(target - self.cam) > self.view_ph * 0.8:
                self.cam = target
            y0 = int(round(self.cam))
        else:
            y0 = 0
        vh = min(self.view_ph, self.ph - y0)
        buf = [bytearray(self.static[y0 + i]) for i in range(vh)]
        # drop targets / standups
        for i, d in enumerate(tb.drops_def):
            if not tb.drop_down[i]:
                sg = d["seg"]
                self.line(buf, sg[0], sg[1], sg[2], sg[3], C["drop"], y0, thick=1.6)
        for i, d in enumerate(tb.targets):
            sg = d["seg"]
            col = C["flash"] if ("target%d" % i) in game.flash else C["target"]
            self.line(buf, sg[0], sg[1], sg[2], sg[3], col, y0, thick=1.4)
        for (x, y, r, m, cid) in tb.circles:
            if cid in game.flash:
                self.disk(buf, x, y, r + 1, C["flash"], y0)
        for i, sl in enumerate(GEOMETRY["slings"]):
            if ("sling%d" % i) in game.flash:
                a, c = sl[0], sl[2]
                self.line(buf, c[0], c[1], a[0], a[1], C["flash"], y0, thick=1.5)
        # lights
        letters = []
        for name, (pos, colname, kind) in tb.lights.items():
            on = game.light_on(name)
            col = C[colname] if on else C.get(colname + "_d", C["white_d"])
            if len(name) > 2 and name[-2] == "_" and name[-1].isalpha() and name[-1].isupper() and name.split("_")[0] in ("lane", "ride", "duck", "shy"):
                letters.append((pos, name[-1], col, on))
                continue
            size = {"arrow": 3.5, "star": 3.5}.get(kind, 2.2)
            self.disk(buf, pos[0], pos[1], size, col, y0)
        # flippers
        for f in tb.flippers:
            ux, uy = math.cos(f.a), math.sin(f.a)
            n = int(f.len / max(s * 0.5, 0.5)) + 1
            for i in range(n + 1):
                t = f.len * i / n
                rad = f.r0 + (f.r1 - f.r0) * t / f.len
                self.disk(buf, f.px + ux * t, f.py + uy * t, rad, C["flipper"], y0)
            self.disk(buf, f.px, f.py, 1.2, C["rubber"], y0)
        # ball
        ball_glyph = None
        if b is not None:
            self.disk(buf, b.x, b.y, max(BALL_R, 1.1 * s), C["ball"], y0)
            if BALL_R / s < 1.3:
                ball_glyph = (b.x / s, b.y / s - y0)
        # pixels -> half blocks
        r0 = self.dmd_rows
        for r in range(self.view_rows):
            ya, yb = 2 * r, 2 * r + 1
            row = cells[r0 + r]
            if ya >= len(buf):
                break
            ta = buf[ya]
            tbb = buf[yb] if yb < len(buf) else ta
            for x in range(self.pw):
                cx = self.tx + x
                if cx >= self.cols:
                    break
                u, d = ta[x], tbb[x]
                row[cx] = (" ", u, u, False) if u == d else ("▀", u, d, PALETTE[u][3])
        # letters (lamp inserts) and the ball glyph
        for (pos, ch, col, on) in letters:
            cx = self.tx + int(pos[0] / s)
            ry = int(pos[1] / s) - y0
            if 0 <= ry < vh:
                r = r0 + ry // 2
                if r0 <= r < self.rows and 0 <= cx < self.cols:
                    bgc = buf[min(ry | 1, len(buf) - 1)][int(pos[0] / s)]
                    cells[r][cx] = (ch, col, C["black"] if on else bgc, True)
        if ball_glyph is not None:
            bx, by = ball_glyph
            if 0 <= by < vh:
                r = r0 + int(by) // 2
                cx = self.tx + int(bx)
                if r0 <= r < self.rows and 0 <= cx < self.cols:
                    _, fg, bg, _ = cells[r][cx]
                    cells[r][cx] = ("●", C["ball"], bg if bg != C["ball"] else C["field"], True)

    def draw_side(self, cells, game):
        x, w = self.side_x, self.side_w
        if w < 12:
            return
        r = self.dmd_rows
        bg = C["black"]
        lines = [
            ("COPPERTILT", C["dmd"], True), ("MIDNIGHT FUNFAIR", C["magenta"], True), ("", 0, False),
        ]
        balls = "".join("●" if i < game.balls_total - game.ball_no + 1 else "○" for i in range(game.balls_total)) if game.state != "attract" else ""
        lines.append(("BALLS  " + balls, C["text"], True))
        if game.extra_balls:
            lines.append(("SHOOT AGAIN +%d" % game.extra_balls, C["ok"], True))
        if game.save_left > 0 and not game.save_used and game.launched and game.state == "play":
            lines.append(("BALL SAVE %ds" % int(math.ceil(game.save_left)), C["ok"], True))
        if game.jackpot_lit:
            lines.append(("JACKPOT LIT: SAUCER", C["gold"], True))
        if game.extra_lit:
            lines.append(("EXTRA BALL LIT", C["orange"], True))
        if game.plunge is not None or (game.table.ball is not None and game.table.ready_to_plunge(game.table.ball) and game.state == "play"):
            n = int(game.charge * 10)
            lines.append(("PLUNGER [" + "#" * n + "." * (10 - n) + "]", C["yellow"], True))
        lines.append(("", 0, False))
        for k, v in (("Z ←", "left flip"), ("M →", "right flip"), ("SPACE ↓", "plunger"),
                     ("X N ↑", "nudge"), ("P", "pause"), ("Q", "quit")):
            lines.append(("%-8s%s" % (k, v), C["hud"], False))
        lines.append(("", 0, False))
        for m in game.log[-max(0, self.view_rows - len(lines) - 1):]:
            lines.append(("» " + m, C["cyan"], False))
        for i, (t, col, bold) in enumerate(lines):
            if r + i >= self.rows:
                break
            if t:
                self.text(cells, r + i, x, t[: w - 1], col, bg, bold)


# ---------------------------------------------------------------- output backends
def cells_to_text(cells):
    return "\n".join("".join(c[0] for c in row).rstrip() for row in cells) + "\n"


def cells_to_ansi(cells):
    out = []
    for row in cells:
        prev = None
        line = []
        for ch, fg, bg, bold in row:
            key = (fg, bg, bold)
            if key != prev:
                line.append("\x1b[0;%s38;5;%d;48;5;%dm" % ("1;" if bold else "", PALETTE[fg][1], PALETTE[bg][1]))
                prev = key
            line.append(ch)
        line.append("\x1b[0m")
        out.append("".join(line))
    return "\n".join(out) + "\n"


def cells_to_json(cells):
    return json.dumps({"rows": [[[ch, "#%02x%02x%02x" % XTERM_RGB[PALETTE[fg][1]], "#%02x%02x%02x" % XTERM_RGB[PALETTE[bg][1]], bold]
                                 for ch, fg, bg, bold in row] for row in cells]})


def write_dumps(args, cells):
    if not args.dump:
        return
    with open(args.dump, "w", encoding="utf-8") as fh:
        fh.write(cells_to_text(cells))
    base = os.path.splitext(args.dump)[0]
    if args.dump_ansi:
        with open(base + ".ansi", "w", encoding="utf-8") as fh:
            fh.write(cells_to_ansi(cells))
    if args.dump_json:
        with open(base + ".json", "w", encoding="utf-8") as fh:
            fh.write(cells_to_json(cells))


def run_headless(args):
    cols, rows = (int(v) for v in args.size.lower().split("x"))
    game = Game(autoplay=args.autoplay, bell=False, hold=args.hold)
    rnd = Renderer()
    rnd.layout(cols, rows)
    frames = args.frames or 300
    now = 0.0
    cells = None
    for _ in range(frames):
        now += 1.0 / FPS
        game.update(1.0 / FPS, now)
        cells = rnd.frame(game)
    write_dumps(args, cells)
    print("headless: %d frames, %dx%d, score %s, ball %d/%d, state %s" % (
        frames, cols, rows, fmt(game.score), game.ball_no, game.balls_total, game.state))
    return 0


KEYMAP = {}


def run_curses(args):
    import curses

    def main(scr):
        curses.curs_set(0)
        scr.nodelay(True)
        scr.keypad(True)
        try:
            curses.set_escdelay(25)
        except AttributeError:
            pass
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        n256 = curses.COLORS >= 256
        pairs = {}
        maxpairs = curses.COLOR_PAIRS - 1

        def attr(fg, bg, bold):
            key = (fg, bg)
            p = pairs.get(key)
            if p is None:
                if len(pairs) < maxpairs:
                    p = len(pairs) + 1
                    f = PALETTE[fg][1] if n256 else PALETTE[fg][2]
                    b = PALETTE[bg][1] if n256 else PALETTE[bg][2]
                    try:
                        curses.init_pair(p, f, b)
                    except (curses.error, ValueError, OverflowError):
                        p = 0
                else:
                    p = 0
                pairs[key] = p
            a = curses.color_pair(p)
            if bold or (not n256 and PALETTE[fg][3]):
                a |= curses.A_BOLD
            return a

        K = {ord("z"): "LEFT", ord("Z"): "LEFT", curses.KEY_LEFT: "LEFT",
             ord("m"): "RIGHT", ord("M"): "RIGHT", ord("/"): "RIGHT", curses.KEY_RIGHT: "RIGHT",
             ord(" "): "PLUNGE", curses.KEY_DOWN: "PLUNGE", 10: "PLUNGE", 13: "PLUNGE", curses.KEY_ENTER: "PLUNGE",
             ord("x"): "NUDGE_L", ord("X"): "NUDGE_L", ord("n"): "NUDGE_R", ord("N"): "NUDGE_R",
             ord("b"): "NUDGE_U", ord("B"): "NUDGE_U", curses.KEY_UP: "NUDGE_U",
             ord("p"): "p", ord("P"): "p", ord("q"): "q", ord("Q"): "q", 27: "ESC"}
        game = Game(autoplay=args.autoplay, bell=args.bell, hold=args.hold)
        rnd = Renderer()
        rows, cols = scr.getmaxyx()
        rnd.layout(cols, rows)
        prev = None
        frame = 0
        last = time.monotonic()
        cells = None
        while not game.quit:
            now = time.monotonic()
            while True:
                try:
                    ch = scr.getch()
                except curses.error:
                    ch = -1
                if ch == -1:
                    break
                if ch == curses.KEY_RESIZE:
                    try:
                        curses.update_lines_cols()
                    except AttributeError:
                        pass
                    rows, cols = scr.getmaxyx()
                    rnd.layout(cols, rows)
                    scr.clear()
                    prev = None
                    continue
                k = K.get(ch)
                if k:
                    game.key(k, now)
            rows2, cols2 = scr.getmaxyx()
            if (rows2, cols2) != (rows, cols):
                rows, cols = rows2, cols2
                rnd.layout(cols, rows)
                scr.clear()
                prev = None
            dt = min(0.1, now - last)
            last = now
            game.update(dt, now)
            if game.beeps:
                game.beeps = 0
                curses.beep()
            cells = rnd.frame(game)
            for r, row in enumerate(cells):
                if prev is not None and r < len(prev) and prev[r] == row:
                    continue
                c = 0
                n = len(row)
                while c < n:
                    ch0, fg, bg, bold = row[c]
                    e = c + 1
                    while e < n and row[e][1] == fg and row[e][2] == bg and row[e][3] == bold:
                        e += 1
                    s = "".join(x[0] for x in row[c:e])
                    if r == len(cells) - 1 and e == n:
                        s = s[:-1]
                    try:
                        scr.addstr(r, c, s, attr(fg, bg, bold))
                    except curses.error:
                        pass
                    c = e
            prev = cells
            scr.refresh()
            frame += 1
            if args.frames and frame >= args.frames:
                break
            spare = 1.0 / FPS - (time.monotonic() - now)
            if spare > 0:
                time.sleep(spare)
        return cells, game

    os.environ.setdefault("ESCDELAY", "25")
    cells, game = curses.wrapper(main)
    if cells is not None:
        write_dumps(args, cells)
    if game.score:
        print("CopperTilt TTY - score %s (high %s)" % (fmt(game.score), fmt(game.high)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="CopperTilt - terminal pinball (Midnight Funfair)")
    ap.add_argument("--autoplay", action="store_true", help="demo: the computer plays")
    ap.add_argument("--frames", type=int, default=0, help="quit after N frames")
    ap.add_argument("--dump", help="write the last screen as text to FILE")
    ap.add_argument("--dump-ansi", action="store_true", help="with --dump: also FILE.ansi (colours)")
    ap.add_argument("--dump-json", action="store_true", help="with --dump: also FILE.json (cells + colours)")
    ap.add_argument("--headless", action="store_true", help="no terminal; simulate and render into a buffer")
    ap.add_argument("--size", default="100x32", help="headless screen size, e.g. 80x24")
    ap.add_argument("--seed", type=int, default=None, help="random seed")
    ap.add_argument("--bell", action="store_true", help="terminal bell on big awards")
    ap.add_argument("--hold", type=float, default=0.45, help="seconds a flipper stays up per key press")
    args = ap.parse_args(argv)
    if args.seed is not None:
        random.seed(args.seed)
    if args.headless:
        return run_headless(args)
    if not sys.stdout.isatty():
        print("coppertilt_tty: needs a terminal (or use --headless)", file=sys.stderr)
        return 2
    return run_curses(args)


if __name__ == "__main__":
    sys.exit(main())
