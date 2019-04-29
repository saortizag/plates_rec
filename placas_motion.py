import cv2
import numpy as np
import imutils
import re
from similarity.normalized_levenshtein import NormalizedLevenshtein
import pandas as pd
import datetime
import time

from openalpr import Alpr
import locale
locale.setlocale(locale.LC_ALL, 'C')


#initialize alpr object.
alpr =  Alpr("us", "/etc/openalpr/openalpr.conf", "/usr/local/src/openalpr/openalpr/runtime_data/")

if not alpr.is_loaded():
    print("Error loading OpenALPR")
    sys.exit(1)

# initialize cv2 video objects.
cap = cv2.VideoCapture("carros.avi")

w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(cap.get(cv2.CAP_PROP_FPS))

#print(w)
#print(h)
#print(fps)

#fourcc = cv2.VideoWriter_fourcc(*'XVID') #codec. each video format has one.
#out = cv2.VideoWriter("rec_placas.avi", fourcc, fps, (w, h))

if not cap.isOpened():
    alpr.unload()
    sys.exit("No abrió el video")

# parameters.
alpr.set_top_n(10)
font = cv2.FONT_HERSHEY_DUPLEX
normalized_levenshtein = NormalizedLevenshtein()
delta_threshold = 12 #10
min_area = 18000
epsilon = 0.500
umbral = 40


###########################
########## MAIN ###########
###########################

frame = 1
prev_frame = None
placa_anterior = "AAA000"
n_carros = 0
n_carros2 = 0
last_car_frame = 0

df = pd.DataFrame(columns = ["tiempo", "cuadro", "placa", "confianza"])

t_inicial = time.time()
while True:

    ret_bool, frame_img_orig = cap.read()
    
    if not ret_bool:
        print("no hay cuadro")
        break
    
    #MOTION DETECTOR.
    frame_img = frame_img_orig.copy() 
    gray_frame_img = cv2.cvtColor(frame_img, cv2.COLOR_BGR2GRAY)
    blurred_gray_frame_img = cv2.GaussianBlur(gray_frame_img, (15, 15), 0)
    
    if frame == 1:
        prev_frame = blurred_gray_frame_img
        frame += 1
        continue

    #operations for motion detector to work
    frameDelta = cv2.absdiff(blurred_gray_frame_img, prev_frame)

    fgmask = cv2.threshold(frameDelta, delta_threshold, 255, cv2.THRESH_BINARY)[1]
    fgmask = cv2.dilate(fgmask, None, iterations=2)
    
    contours = cv2.findContours(fgmask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = imutils.grab_contours(contours)
    
    #define movement as a function of the contained area by the contour.
    mov = False # initialize movement variable
    
    for contour in contours:
        if cv2.contourArea(contour) < min_area:
            continue
        (x, y, w, h) = cv2.boundingRect(contour)
        cv2.rectangle(frame_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        mov = True #if there's movement, change mov to true.

    
    #ALPR RESULTS
    frame_plate = frame_img_orig.copy() #copy to work on.

    t_mov = time.time()
    if mov:

        # the results dictionary generated by alpr.
        results = alpr.recognize_ndarray(frame_img_orig)

        if results["results"]:
            # CONTADOR 2 #
            if frame - last_car_frame >= umbral:
                n_carros2 += 1
            last_car_frame = frame

        for una_placa in results["results"]: #for each plate on the frame.

            # LÍNEAS #
            cv2.line(frame_plate,
                     (una_placa["coordinates"][0]["x"], una_placa["coordinates"][0]["y"]), 
                     (una_placa["coordinates"][1]["x"], una_placa["coordinates"][1]["y"]),
                     (255,0,0), 
                     5
            )
            cv2.line(frame_plate,
                     (una_placa["coordinates"][1]["x"], una_placa["coordinates"][1]["y"]), 
                     (una_placa["coordinates"][2]["x"], una_placa["coordinates"][2]["y"]),
                     (255,0,0), 
                     5
            )
            cv2.line(frame_plate,
                     (una_placa["coordinates"][2]["x"], una_placa["coordinates"][2]["y"]), 
                     (una_placa["coordinates"][3]["x"], una_placa["coordinates"][3]["y"]),
                     (255,0,0), 
                     5
            )
            cv2.line(frame_plate,
                     (una_placa["coordinates"][3]["x"], una_placa["coordinates"][3]["y"]), 
                     (una_placa["coordinates"][0]["x"], una_placa["coordinates"][0]["y"]),
                     (255,0,0), 
                     5
            )    

            if una_placa["candidates"][0]["plate"]:
                now = datetime.datetime.now()

                if re.match(r"^[A-Z]{3}[0-9]{3}$", una_placa["candidates"][0]["plate"]):

                    df = df.append( {"tiempo": now.time(), "cuadro": frame, "placa": una_placa["candidates"][0]["plate"], "confianza": una_placa["candidates"][0]["confidence"]}, ignore_index=True)

                    # CONTADOR 1 #
                    placa_actual = una_placa["candidates"][0]["plate"]
                    #print(placa_actual, placa_anterior, n_carros)
                    if normalized_levenshtein.distance(placa_actual, placa_anterior) >= epsilon:
                        n_carros += 1
                        placa_anterior = placa_actual
                    
                    # PLACA TOP CANDIDATE #
                    cv2.putText(frame_plate,
                                una_placa["candidates"][0]["plate"] + "(confianza: " + str(una_placa["candidates"][0]["confidence"]) + ")",
                                (una_placa["coordinates"][0]["x"], una_placa["coordinates"][0]["y"]),
                                font, 1.0, (1, 1, 255),
                                1
                    )
                                
                    print(str(frame), una_placa["candidates"][0]["plate"] + " (confianza: " + str(una_placa["candidates"][0]["confidence"]) + ")")

                else:
                    df = df.append( {"tiempo": now.time(), "cuadro": frame, "placa": np.nan, "confianza": np.nan}, ignore_index=True)


                # Select the plates from the image using the plates location.
                rows, cols, colors = frame_plate.shape
                pts1 = np.float32([[results["results"][0]["coordinates"][0]["x"], results["results"][0]["coordinates"][0]["y"] ],
                                   [results["results"][0]["coordinates"][1]["x"], results["results"][0]["coordinates"][1]["y"]],
                                   [results["results"][0]["coordinates"][3]["x"], results["results"][0]["coordinates"][3]["y"]], 
                                   [results["results"][0]["coordinates"][2]["x"], results["results"][0]["coordinates"][2]["y"]] ])

                pts2 = np.float32([[0,0],[1280,0],[0,720],[1280,720]])
                M = cv2.getPerspectiveTransform(pts1, pts2)
                placa_grande = cv2.warpPerspective(frame_plate, M, (cols, rows))
                placa = cv2.resize(placa_grande, (0,0), fx=0.33, fy=0.33) 
                
                cv2.imwrite("placas/"+str(len(df.index)-1)+".jpg", placa)

    print("tiempo del cuadro: "+str(time.time()-t_mov))

    #write the .csv file.
    df.to_csv("placas/placas_detectadas.csv")

    #puts the number of the frame on each image
    cv2.putText(frame_plate, str(frame), (26, 621), font, 2.0, (0, 0, 255), 1)
    cv2.putText(fgmask, str(frame), (26, 621), font, 2.0, (0, 0, 255), 1)
    cv2.putText(frame_img, str(frame), (26, 621), font, 2.0, (0, 0, 255), 1)

    #puts the counter on the frame
    cv2.putText(frame_plate, str(n_carros), (260, 621), font, 2.0, (0, 255, 255), 1)
    cv2.putText(frame_plate, str(n_carros2), (520, 621), font, 2.0, (65, 200, 255), 1)
    
    #show the interesting things
    cv2.imshow("movimiento", frame_img)
    cv2.imshow("mask", fgmask)
    cv2.imshow("Video con placas", frame_plate)
    

    #writes a new video
    #out.write(frame_plate)
    
    #key for stopping video
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break

    #change the iterators for the motion detector
    if (frame - 1) % 1 == 0:
        prev_frame = blurred_gray_frame_img   
    frame += 1
        
cap.release()
cv2.destroyAllWindows()
alpr.unload()            
#out.release()

print("tiempo total: "+str(time.time() - t_inicial))
