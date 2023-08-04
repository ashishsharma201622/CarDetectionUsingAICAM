from pathlib import Path
import cv2
import depthai as dai
import time
import tkinter as tk
from tkinter import ttk
import os, io
import psycopg2
from PIL import Image, ImageTk
from google.cloud import vision
import re
import datetime
from tkinter import messagebox
import manage
import urllib.request

root = tk.Tk()
root.configure(background="grey")
root.title("車の検出")
root.geometry("800x407")
root.resizable(False, False)

save_btn = tk.Button(root, background="white", foreground="black", text="登録", font="Cambria 25",
                    command=lambda: call_to_DB())
save_btn.grid(row=0, column=0, sticky="nw", pady=340, padx=0)

label_frame = tk.Frame(root, background="white", width=20, height=20)  # frame for detected objects name
label_frame.grid(row=0, column=0, sticky="nw", pady=2, padx=0)

canvas = tk.Canvas(root, width=301, height=301, background="grey")
canvas.grid(row=0, column=0, sticky="nw", pady=35, padx=0)

details_frame = tk.Frame(root, background="gray", width=450, height=360)
details_frame.grid(row=0, column=0, sticky="nw", padx=310, pady=38)


def call_to_DB():
    manage.main()
    url = ' http://127.0.0.1:8000/'
    urllib.request.urlopen(url)

# 写真保存→文字検出
def call_save_image(frame):
    try:
        os.makedirs("captured_images")
    except FileExistsError:
        pass

    for i in range(1):
        if os.path.exists(f"captured_images/saved{i}.jpg"):
            while os.path.exists(f"captured_images/saved{i}.jpg"):
                i += 1
            file_name = f"captured_images/saved{i}.jpg"
        else:
            # If the file does not exist, save the file with the original file name
            file_name = f"captured_images/saved{i}.jpg"
            print("image saved successfully")
        log_time = datetime.datetime.now()
        lbl_time = log_time.strftime('%Y年%m月%d日 %H:%M')
        cv2.imwrite(file_name, frame)
        # time.sleep(1)

    # 　ナンバープレート文字認識
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r'../models/credentials.json'#ラズパイパス
    image_files = os.listdir("captured_images")
    sorted_images = sorted(image_files, key=lambda x: os.path.getmtime(os.path.join("captured_images", x)))

    last_image = sorted_images[-1] if sorted_images else None
    if last_image:
        path = os.path.join("captured_images", last_image)
        # Instantiates a client
        client = vision.ImageAnnotatorClient()
        img = Image.open(path)
        image_width = img.width
        image_height = img.height
        # Loads the image into memory
        with io.open(path, 'rb') as image_file:
            content = image_file.read()
        image = vision.Image(content=content)
        objects = client.object_localization(image=image)
        label = objects.localized_object_annotations
        plate_flag = 0
        all_combined = ''

        for labels in label:
            if labels.name == 'License plate':
                plate_flag = 1
                left = round(image_width * labels.bounding_poly.normalized_vertices[0].x)
                upper = round(image_height * labels.bounding_poly.normalized_vertices[0].y)
                right = round(image_width * labels.bounding_poly.normalized_vertices[2].x)
                lower = round(image_height * labels.bounding_poly.normalized_vertices[2].y)
        # 画像を開く
        plate_name = ''
        if plate_flag == 1:
            img = Image.open(path)
            # 画像を切り抜く
            img_roi = img.crop((left, upper, right, lower))
            # 切り抜いた画像の保存
            if not os.path.exists('plate_image'):
                os.makedirs('plate_image')
            # 画像をRGB形式に変換する
            if img_roi.mode != "RGB":
                img_roi = img_roi.convert("RGB")
            img_roi.save("plate_image/" + last_image)

            plate_name = os.path.abspath('plate_image/' + last_image)
            with io.open(plate_name, 'rb') as image_file:
                content = image_file.read()
            image = vision.Image(content=content)
            response = client.document_text_detection(
                image=image,
                image_context={'language_hints': ['ja']}
            )
            # レスポンスからテキストデータを抽出
            kanji = ''
            class_number = ''
            hira = ''
            assign_number = ''
            paraflag = 0

            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            for symbol in word.symbols:
                                # print(symbol.text)
                                # 事務局番号
                                if re.compile(r'^[\u4E00-\u9FD0]+$').fullmatch(symbol.text) and paraflag == 0:
                                    kanji += symbol.text
                                # 自動車区分番号３桁まで
                                elif re.compile('[0-9]+').fullmatch(symbol.text) and paraflag == 0:
                                    class_number += symbol.text
                                # ひらがな
                                elif re.compile(r'^[あ-ん]+$').fullmatch(symbol.text) and paraflag != 0:
                                    hira += symbol.text
                                # 一連指定番号
                                elif re.compile('[0-9]+').fullmatch(symbol.text) and paraflag != 0:
                                    assign_number += symbol.text
                        paraflag += 1
            if kanji != '' and class_number != '' and hira != '' and assign_number != '':
                all_combined = kanji + class_number + hira + assign_number
                print("all combined " + all_combined)

            # DB照合
            if all_combined != "":
                number_list = con_db()
                for number in number_list:
                    if number[0] == all_combined:
                        alert_flag = 1
                        result = '登録されている車'
                        break  # Exit the loop if car is detected

                    else:  # Executed if the loop completes without a break statement (no car detected)
                        alert_flag = 2
                        result = '登録されていない車'

                # logを保存
                conn = psycopg2.connect(host='10.16.76.108',user='postgres',password='takaya',port='5432', database='car_number')    
                cursor = conn.cursor()
                cursor.execute("SELECT number FROM carnumber_log")


                print("Detected number plate is: ", all_combined)

                sql = "INSERT INTO carnumber_log  (number,time,result,image) VALUES(%s, %s, %s, %s)"
                cursor.execute(sql, (str(all_combined), log_time, result, file_name))
                conn.commit()
                conn.close()
            else:
                # プレートはあったが文字が正しく認識できなかったとき
                alert_flag = 4

        else:
            #プレートが認識できなかった場合
            alert_flag = 3
    return alert_flag,all_combined,lbl_time,file_name,plate_name


def result_label(res_label, distance):  # for saving car or person or something else....
    info_label = tk.Label(label_frame, text=f" 結果  ：{res_label}", background="grey", foreground="white",
                          font=("Cambria", 19), width=21)
    info_label.grid(row=0, column=0)

    info_label1 = tk.Label(label_frame, text=f" 距離：{distance}", background="grey", foreground="white",
                           font=("Cambria", 19), width=21)
    info_label1.grid(row=0, column=1)
    return res_label, distance


def main():
    import sys

    nnBlobPath = str(
        (Path(__file__).parent / Path(r'mobilenet-ssd_openvino_2021.4_6shave.blob')).resolve().absolute())#ラズパイパス
    if len(sys.argv) > 1:
        nnBlobPath = sys.argv[1]

    if not Path(nnBlobPath).exists():
        import sys

        # raise FileNotFoundError(f'Required file/s not found, please run install_requirements.py"')

    # MobilenetSSD label texts
    labelMap = ["background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus", "car", "cat", "chair", "cow",
                "diningtable", "dog", "horse", "motorbike", "person", "pottedplant", "sheep", "sofa", "train",
                "tvmonitor"]

    syncNN = True

    # Create pipeline
    pipeline = dai.Pipeline()

    # Define sources and outputs
    camRgb = pipeline.create(dai.node.ColorCamera)
    spatialDetectionNetwork = pipeline.create(dai.node.MobileNetSpatialDetectionNetwork)
    monoLeft = pipeline.create(dai.node.MonoCamera)
    monoRight = pipeline.create(dai.node.MonoCamera)
    stereo = pipeline.create(dai.node.StereoDepth)

    xoutRgb = pipeline.create(dai.node.XLinkOut)
    xoutNN = pipeline.create(dai.node.XLinkOut)
    xoutDepth = pipeline.create(dai.node.XLinkOut)

    xoutRgb.setStreamName("rgb")
    xoutNN.setStreamName("detections")
    xoutDepth.setStreamName("depth")

    # Properties
    camRgb.setPreviewSize(300, 300)
    camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    camRgb.setInterleaved(False)
    camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)

    monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    monoLeft.setBoardSocket(dai.CameraBoardSocket.LEFT)
    monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    monoRight.setBoardSocket(dai.CameraBoardSocket.RIGHT)

    # Setting node configs
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
    # Align depth map to the perspective of RGB camera, on which inference is done
    stereo.setDepthAlign(dai.CameraBoardSocket.RGB)
    stereo.setOutputSize(monoLeft.getResolutionWidth(), monoLeft.getResolutionHeight())

    spatialDetectionNetwork.setBlobPath(nnBlobPath)
    spatialDetectionNetwork.setConfidenceThreshold(0.5)
    spatialDetectionNetwork.input.setBlocking(False)
    spatialDetectionNetwork.setBoundingBoxScaleFactor(0.5)
    spatialDetectionNetwork.setDepthLowerThreshold(100)
    spatialDetectionNetwork.setDepthUpperThreshold(5000)

    # Linking
    monoLeft.out.link(stereo.left)
    monoRight.out.link(stereo.right)

    camRgb.preview.link(spatialDetectionNetwork.input)
    if syncNN:
        spatialDetectionNetwork.passthrough.link(xoutRgb.input)
    else:
        camRgb.preview.link(xoutRgb.input)

    spatialDetectionNetwork.out.link(xoutNN.input)

    stereo.depth.link(spatialDetectionNetwork.inputDepth)
    spatialDetectionNetwork.passthroughDepth.link(xoutDepth.input)

    with dai.Device(pipeline) as device:
        # Output queues will be used to get the rgb frames and nn data from the outputs defined above
        previewQueue = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        detectionNNQueue = device.getOutputQueue(name="detections", maxSize=4, blocking=False)
        depthQueue = device.getOutputQueue(name="depth", maxSize=4, blocking=False)

        startTime = time.monotonic()
        counter = 0
        color = (255, 255, 255)
        b_distance = 1500
        image_flag = True
        alert_flag =0

        while True:
            if device.getOutputQueue("rgb").has():
                in_rgb = device.getOutputQueue("rgb").get()
                # Convert OpenCV image to PIL image
                img = cv2.cvtColor(in_rgb.getCvFrame(), cv2.COLOR_BGR2RGB)

                pil_img = Image.fromarray(img)
                # Update the PhotoImage object
                photo_img = ImageTk.PhotoImage(pil_img)
                # Draw the PhotoImage on the canvas
                canvas_img = canvas.create_image(0, 0, anchor=tk.NW, image=photo_img)
                canvas.itemconfig(canvas_img, image=photo_img)
                canvas.update()
                inPreview = previewQueue.get()
                inDet = detectionNNQueue.get()
                depth = depthQueue.get()

                counter += 1

                frame = inPreview.getCvFrame()

                depthFrame = depth.getFrame()  # depthFrame values are in millimeters

                depthFrameColor = cv2.normalize(depthFrame, None, 255, 0, cv2.NORM_INF, cv2.CV_8UC1)
                depthFrameColor = cv2.equalizeHist(depthFrameColor)
                depthFrameColor = cv2.applyColorMap(depthFrameColor, cv2.COLORMAP_HOT)

                detections = inDet.detections

                # If the frame is available, draw bounding boxes on it and show the frame
                height = frame.shape[0]
                width = frame.shape[1]
                for detection in detections:
                    roiData = detection.boundingBoxMapping
                    roi = roiData.roi
                    roi = roi.denormalize(depthFrameColor.shape[1], depthFrameColor.shape[0])
                    topLeft = roi.topLeft()
                    bottomRight = roi.bottomRight()
                    xmin = int(topLeft.x)
                    ymin = int(topLeft.y)
                    xmax = int(bottomRight.x)
                    ymax = int(bottomRight.y)
                    cv2.rectangle(depthFrameColor, (xmin, ymin), (xmax, ymax), color, cv2.FONT_HERSHEY_SCRIPT_SIMPLEX)

                    # Denormalize bounding box
                    x1 = int(detection.xmin * width)
                    x2 = int(detection.xmax * width)
                    y1 = int(detection.ymin * height)
                    y2 = int(detection.ymax * height)
                    try:
                        res_label = labelMap[detection.label]
                    except:
                        res_label = detection.label
                    distance = int(detection.spatialCoordinates.z)

                    if int(detection.spatialCoordinates.z) > 1000:
                        alert_flag = 0
                        image_flag = True
                        b_distance = 1000
                    elif int(detection.spatialCoordinates.z) < 400:
                        b_distance = 0
                    elif 400 < int(detection.spatialCoordinates.z) < 1000:
                        distance = int(detection.spatialCoordinates.z)
                        if b_distance > distance and b_distance - distance > 100:
                            if image_flag == True:
                                if labelMap[detection.label] == "car":
                                    start = time.time()
                                    b_distance = distance
                                    image_flag = False
                                    result = call_save_image(frame)
                                    alert_flag = result[0]
                                    print("車を認識してから結果が返ってくるまで",time.time() - start)
                                    if alert_flag == 3:
                                        print('プレートが認識されませんでした。')
                                        file_name = result[3]
                                        os.remove(file_name)
                                        image_flag = True
                                    elif alert_flag == 4:
                                        print('文字が認識できなかった')
                                        file_name = result[3]
                                        path = result[4]
                                        os.remove(file_name)
                                        os.remove(path)
                                        image_flag = True
                                    else:
                                        path = result[4]
                                        # os.remove(path)
                    detected_car_label_str = tk.StringVar()
                    detected_car_label_str.set("検出中")
                    detected_car_label = tk.Label(root, foreground="black", border=9, textvariable=detected_car_label_str,width=10,
                                        borderwidth=5, bg="white", font=("Cambria", 17))
                    
                    live_result = tk.StringVar()
                    live_result.set("")
                    car_platelbl = tk.Label(details_frame, background="black", foreground="white", textvariable=live_result, font=("", 15),width=30)
                    time_result = tk.StringVar()
                    time_result.set("")
                    time_plate = tk.Label(details_frame, background="black", foreground="white", textvariable=time_result, font=("", 15),width=30)
                    if alert_flag == 1:
                        detected_car_label_str.set("タカヤの車")
                        detected_car_label.configure(foreground="black", bg="green")
                        live_result.set("ナンバー:"+ result[1])
                        time_result.set("時間:"+ result[2])
                    elif alert_flag == 2:
                        detected_car_label_str.set("車が来ました")
                        detected_car_label.configure(foreground="white", bg="red")
                        live_result.set("ナンバー:"+ result[1])
                        time_result.set("時間:"+ result[2])

                    detected_car_label.grid(row=0, column=0, sticky="ne", padx=621, pady=1)
                    car_platelbl.grid(row=0, column=0,padx=100, pady=50)
                    time_plate.grid(row=1, column=0,pady=5)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), cv2.FONT_HERSHEY_SIMPLEX)
                    # cv2.putText(frame, "NN fps: {:.2f}".format(fps), (2, frame.shape[0] - 4), cv2.FONT_HERSHEY_TRIPLEX, 0.4,
                    #             (255, 0, 255))
                    # cv2.putText(frame, (2, frame.shape[0] - 4), cv2.FONT_HERSHEY_TRIPLEX, 0.4,(255, 0, 255))
                    # cv2.putText(frame, str(label), (x1 + 10, y1 + 20), cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255)
                    # cv2.putText(frame, "{:.2f}".format(detection.confidence*100), (x1 + 10, y1 + 35), cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255)
                    # cv2.putText(frame, f"X: {int(detection.spatialCoordinates.x)} mm", (x1 + 10, y1 + 50), cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255)
                    # cv2.putText(frame, f"Y: {int(detection.spatialCoordinates.y)} mm", (x1 + 10, y1 + 65), cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255
                    # cv2.putText(frame, f"Z: {int(detection.spatialCoordinates.z)} mm", (x1 + 10, y1 + 80), cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255)
                    result_label(res_label, distance)


def con_db():
    conn = psycopg2.connect(host='10.16.76.108',user='postgres',password='takaya',port='5432', database='car_number')    
    cursor = conn.cursor()
    cursor.execute("SELECT number FROM number_table")
    number_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return number_list


if __name__ == "__main__":
    main()
