# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import cv2
import numpy as np
import logging
import time
from pipeline.pipeline_executor import PipelinePostProcessingOptions, ProcessingPipeline

class GPUProcessingPipeline(ProcessingPipeline):
    timers = {
        "total": [],
        "read": [],
        "pre-process": [],
        "optical flow": [],
        "post-process": []
    }

    def __init__(self, resized_frame_width: int, resized_frame_height: int, post_processing: PipelinePostProcessingOptions) -> None:
        super().__init__()
        self.resized_frame_width = resized_frame_width
        self.resized_frame_height = resized_frame_height
        self.post_processing = post_processing

    def process(self, video: str):

        output_video = video.replace(".mp4", "_processed.mp4")

        cap = cv2.VideoCapture(video)
        fps = cap.get(cv2.CAP_PROP_FPS)
        num_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        ret, previous_frame = cap.read()

        num_devices = cv2.cuda.getCudaEnabledDeviceCount()
        if num_devices > 0:
            logging.info("Total CUDA devices: %s", num_devices)
            for i in range(num_devices):
                device = cv2.cuda.DeviceInfo(i)

                logging.info("\nGPU-ID: %s", i)
                try: 
                    logging.info("Name: %s", device.name())
                except:
                    logging.info("Name: N/A")
                
                logging.info("Memory: %s MB", device.totalMemory())
                logging.info("Version: %s.%s", device.majorVersion(), device.minorVersion())

        else:
            raise Exception("error: No GPU devices available. Please check your CUDA installation.")
            
        logging.info("Source video has %s frames with %s rate.", num_frames, fps)

        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        new_vid = cv2.VideoWriter(output_video, fourcc, fps, (self.resized_frame_width, self.resized_frame_height))        

        if ret:
            frame = cv2.resize(previous_frame, (self.resized_frame_width, self.resized_frame_height))

            gpu_frame = cv2.cuda_GpuMat()
            gpu_frame.upload(frame)

            previous_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            gpu_previous = cv2.cuda_GpuMat()
            gpu_previous.upload(previous_frame)

            gpu_hsv = cv2.cuda_GpuMat(gpu_frame.size(), cv2.CV_32FC3)
            gpu_hsv_8bit_unsigned = cv2.cuda_GpuMat(gpu_frame.size(), cv2.CV_8UC3)

            gpu_hue = cv2.cuda_GpuMat(gpu_frame.size(), cv2.CV_32FC1)
            gpu_saturation = cv2.cuda_GpuMat(gpu_frame.size(), cv2.CV_32FC1)
            gpu_value = cv2.cuda_GpuMat(gpu_frame.size(), cv2.CV_32FC1)

            # set saturation to 1
            gpu_saturation.upload(np.ones_like(previous_frame, np.float32))

            while True:
                start_full_time = time.time()

                # Reading frames
                start_read_time = time.time()
                ret, frame = cap.read()
                gpu_frame.upload(frame)

                end_read_time = time.time()
                self.timers["read"].append(end_read_time - start_read_time)

                if not ret:
                    break

                # Pre-processing
                start_pre_time = time.time()
                gpu_frame = cv2.cuda.resize(gpu_frame, (self.resized_frame_width, self.resized_frame_height))
                gpu_current = cv2.cuda.cvtColor(gpu_frame, cv2.COLOR_BGR2GRAY)

                end_pre_time = time.time()
                self.timers["pre-process"].append(end_pre_time - start_pre_time)

                # Optical flow
                start_of = time.time()
                gpu_flow = cv2.cuda_FarnebackOpticalFlow.create(
                    5, 0.5, False, 15, 3, 5, 1.2, 0,
                )
                gpu_flow = cv2.cuda_FarnebackOpticalFlow.calc(
                    gpu_flow, gpu_previous, gpu_current, None,
                )
                end_of = time.time()
                self.timers["optical flow"].append(end_of - start_of)

                # Post processing
                start_post_time = time.time()

                if self.post_processing == PipelinePostProcessingOptions.HEATMAP or self.post_processing == PipelinePostProcessingOptions.BOTH:
                    bgr_frame = self.draw_flow_heatmap(gpu_flow, gpu_hsv, gpu_hsv_8bit_unsigned, gpu_hue, gpu_saturation, gpu_value).download()
                else:
                    bgr_frame = gpu_frame.download()
                    
                if self.post_processing == PipelinePostProcessingOptions.ARROWS or self.post_processing == PipelinePostProcessingOptions.BOTH:
                    flow = gpu_flow.download()
                    bgr_frame = self.draw_flow_vectors(bgr_frame, flow)

                # save new frame
                gpu_previous = gpu_current
                new_vid.write(bgr_frame)

                end_post_time = time.time()
                self.timers["post-process"].append(end_post_time - start_post_time)
                end_full_time = time.time()
                self.timers["total"].append(end_full_time - start_full_time)

        cap.release()
        new_vid.release()

        output = {}
        for stage, seconds in self.timers.items():
            output[stage] =  "{:0.3f}".format(sum(seconds))

        output["video fps"] = "{:0.3f}".format(fps)

        of_fps = (num_frames - 1) / sum(self.timers["optical flow"])
        output["optical flow fps"] = "{:0.3f}".format(of_fps)

        full_fps = (num_frames - 1) / sum(self.timers["total"])
        output["full pipeline fps"] = "{:0.3f}".format(full_fps)

        return { 
            "device": "gpu",
            "stats": output, 
            "video": '/' + output_video
        }

    def draw_flow_heatmap(self, flow, hsv, hsv_8bit_unsigned, hue, saturation, value):
        gpu_flow_x = cv2.cuda_GpuMat(flow.size(), cv2.CV_32FC1)
        gpu_flow_y = cv2.cuda_GpuMat(flow.size(), cv2.CV_32FC1)
        cv2.cuda.split(flow, [gpu_flow_x, gpu_flow_y])

        # Convert from cartesian to polar coordinates for magnitude and angle
        gpu_magnitude, gpu_angle = cv2.cuda.cartToPolar(
            gpu_flow_x, gpu_flow_y, angleInDegrees=True,
        )

        # Set the value to a normalized magnitude from 0 to 1
        value = cv2.cuda.normalize(gpu_magnitude, 0.0, 1.0, cv2.NORM_MINMAX, -1)

        # Get the angle from the GPU
        angle = gpu_angle.download()
        angle *= (1 / 360.0) * (180 / 255.0)

        # Trick is setting the hue of the image buffer to the angle of the flow
        hue.upload(angle)

        # Merge all the channels
        cv2.cuda.merge([hue, saturation, value], hsv)

        # Convert to 255 scale
        hsv.convertTo(cv2.CV_8U, hsv_8bit_unsigned, 255.0)

        # Lastly returning converted HSV to BGR
        return cv2.cuda.cvtColor(hsv_8bit_unsigned, cv2.COLOR_HSV2BGR)
        
