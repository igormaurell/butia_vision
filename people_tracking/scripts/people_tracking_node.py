#!/usr/bin/env python

import cv2
import rospy
import os
import rospkg

from cv_bridge import CvBridge

from people_tracking_ros.PeopleTracking import PeopleTracking

from butia_vision_msgs.msg import Recognitions, Description, BoundingBox, RGBDImage
from std_msgs.msg import Header
from sensor_msgs.msg import Image

from butia_vision_msgs.srv import ImageRequest, SegmentationRequest, StartTracking, StopTracking

BRIDGE = CvBridge()

probability_threshold=None
segmentation_type=None
queue_size=None

people_tracking=None

tracker_publisher=None
tracker_subscriber=None

start_service=None
stop_service=None

image_request_client=None 
segmentation_request_client=None

frame=None
descriptions=None

PACK_DIR = rospkg.RosPack().get_path('people_tracking')

def debug(cv_frame, tracker, dets):
    for track in tracker.tracks:
        if not track.is_confirmed() or track.time_since_update > 1:
            continue

        bbox = track.to_tlbr()
        id_num= str(track.track_id)
        features = track.features

        cv2.rectangle(cv_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])),(255,255,255), 2)
        cv2.putText(cv_frame, str(id_num),(int(bbox[0]), int(bbox[1])),0, 5e-3 * 200, (0,255,0),2)

        for det in dets:
            bbox = det.to_tlbr()
            cv2.rectangle(cv_frame,(int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])),(255,255,0), 2)

    cv2.imshow('cv_frame',cv_frame)
    cv2.waitKey(1)
    

#Tracking people in real time
def peopleDetectionCallBack(recognition):
    frame_id = recognition.image_header.seq
    req = image_request_client(frame_id)
    frame = req.rgbd_image.rgb
    descriptions = recognition.descriptions
    cv_frame = BRIDGE.imgmsg_to_cv2(frame, desired_encoding = 'rgb8')
    frame_rgb = cv2.cvtColor(cv_frame,cv2.COLOR_BGR2RGB)
    people_tracking.setFrame(recognition.image_header, recognition.recognition_header, frame_id, frame_rgb.copy())

    img_size = frame.height * frame.width
    
    for description in descriptions:
        if(description.probability < probability_threshold):
            descriptions.remove(description)

    tracker, detections = people_tracking.track(descriptions)

    debug(frame_rgb.copy(), tracker, detections)

    if people_tracking.trackingPerson is not None:
        response = Recognition()
        response.image_header = recognition.image_header
        response.recognition_header = recognition.recognition_header
        response.descriptions = [Description()]
        response.descriptions[0].probability = people_tracking.trackingPerson.track_id
        BBbox = BoundingBox()
        BBbox.minX = people_tracking.trackingPerson.to_tlwh()[0]
        BBbox.minY = people_tracking.trackingPerson.to_tlwh()[1]
        BBbox.width = people_tracking.trackingPerson.to_tlwh()[2]
        BBbox.height = people_tracking.trackingPerson.to_tlwh()[3]
        response.descriptions[0].bounding_box = BBbox
        tracker_publisher.publish(response)

    


def startTracking(start):
    people_tracking.startTrack()
    return start

def stopTracking(stop):
    people_tracking.stopTrack()
    return stop

if __name__ == '__main__':
    rospy.init_node('people_tacking_node', anonymous = True)
    
    probability_threshold = rospy.get_param("/people_tracking/thresholds/probability", 0.5)
    
    queue_size = rospy.get_param("/people_tracking/queue/size", 20)

    param_start_service = rospy.get_param("/services/people_tracking/start_tracking", "/butia_vision/pt/start")
    param_stop_service = rospy.get_param("/services/people_tracking/stop_tracking", "/butia_vision/pt/stop")
    param_image_request_service = rospy.get_param("/services/image_server/image_request", "/butia_vision/is/image_request")

    param_people_detection_topic = rospy.get_param("/topics/object_recognition/people_detection", "/butia_vision/or/people_detection")
    param_people_tracking_topic = rospy.get_param("/topics/people_tracking/people_tracking", "/butia_vision/pt/people_tracking")

    tracker_publisher = rospy.Publisher(param_people_tracking_topic, Recognitions, queue_size = 10)
    tracker_subscriber = rospy.Subscriber(param_people_detection_topic, Recognitions, peopleDetectionCallBack, queue_size = 10)

    start_service = rospy.Service(param_start_service, StartTracking, startTracking)
    stop_service = rospy.Service(param_stop_service, StopTracking, stopTracking)
    
    rospy.wait_for_service(param_image_request_service)
    try:
        image_request_client = rospy.ServiceProxy(param_image_request_service, ImageRequest)
    except rospy.ServiceException, e:
        print "Service call failed %s"%e
    
    models_dir = os.path.join(PACK_DIR, 'models')
    model_file = os.path.join(models_dir, 'mars-small128.pb')

    people_tracking = PeopleTracking(model_file)

    rospy.spin()
    

