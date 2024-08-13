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

class CPUProcessingPipeline(ProcessingPipeline):
    timers = {
        "total": [],
        "read": [],
        "pre-process": [],
        "optical flow": [],
        "post-process": []
    }

    previous_frame = None

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

        logging.info("CPU pipeline.")
        logging.info("Source video has %s frames with %s rate.", num_frames, fps)

        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        new_vid = cv2.VideoWriter(output_video, fourcc, fps, (self.resized_frame_width, self.resized_frame_height))        

        if ret:
            cpu_frame = cv2.resize(previous_frame, (self.resized_frame_width, self.resized_frame_height))
            previous_frame = cv2.cvtColor(cpu_frame, cv2.COLOR_BGR2GRAY)

            hsv = np.zeros_like(cpu_frame, np.float32)
            hsv[..., 1] = 1.0

            while True:
                # Reading frame
                start_full_time = time.time()
                start_read_time = time.time()

                ret, cpu_frame = cap.read()

                end_read_time = time.time()
                self.timers["read"].append(end_read_time - start_read_time)

                if not ret:
                    break

                # Pre-processing
                start_pre_time = time.time()

                cpu_frame = cv2.resize(cpu_frame, (self.resized_frame_width, self.resized_frame_height))
                cpu_current = cv2.cvtColor(cpu_frame, cv2.COLOR_BGR2GRAY)

                end_pre_time = time.time()
                self.timers["pre-process"].append(end_pre_time - start_pre_time)

                # Optical flow
                start_of = time.time()
                flow = cv2.calcOpticalFlowFarneback(
                        previous_frame, cpu_current, None, 0.5, 5, 15, 3, 5, 1.2, 0,
                    )
                
                end_of = time.time()
                self.timers["optical flow"].append(end_of - start_of)

                # Post processing
                start_post_time = time.time()

                if self.post_processing == PipelinePostProcessingOptions.HEATMAP or self.post_processing == PipelinePostProcessingOptions.BOTH:
                    bgr_frame = self.draw_flow_heatmap(flow, hsv)
                else:
                    bgr_frame = cpu_frame

                if self.post_processing == PipelinePostProcessingOptions.ARROWS or self.post_processing == PipelinePostProcessingOptions.BOTH:
                    bgr_frame = self.draw_flow_vectors(bgr_frame, flow)

                # Saving new frame
                previous_frame = cpu_current
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

        print(output)

        return { 
            "device": "cpu",
            "stats": output, 
            "video": '/' + output_video 
        }

    def draw_flow_heatmap(self, flow, hsv):
        magnitude, angle = cv2.cartToPolar(
            flow[..., 0], flow[..., 1], angleInDegrees=True,
        )

        hsv[..., 0] = angle * ((1 / 360.0) * (180 / 255.0))

        hsv[..., 2] = cv2.normalize(
            magnitude, None, 0.0, 1.0, cv2.NORM_MINMAX, -1,
        )

        hsv_8u = np.uint8(hsv * 255.0)
        return cv2.cvtColor(hsv_8u, cv2.COLOR_HSV2BGR)
