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

import logging
import cv2
import copy
from enum import Enum

class ProcessingPipelineInterface:
    def process(self, video: str):
        raise NotImplementedError("Method not implemented")

class PipelineType(str, Enum):
    GPU = 'gpu'
    CPU = 'cpu'

class PipelinePostProcessingOptions(str, Enum):
    NONE = 'none'
    HEATMAP = 'heatmap'
    ARROWS = 'arrows'
    BOTH = 'both'

class ProcessingPipeline(ProcessingPipelineInterface):
    def draw_flow_vectors(self, bgr_frame, flow):
        vector_frame = copy.deepcopy(bgr_frame)
        step = 32
        h, w = bgr_frame.shape[:2]
        for y in range(0, h, step):
            for x in range(0, w, step):
                fx, fy = flow[y, x]
                cv2.arrowedLine(vector_frame, (x, y), (int(x + fx), int(y + fy)), (0, 255, 0), 1, tipLength=0.5)

        return vector_frame

class PipelineExecutor:
    @staticmethod
    def execute(pipeline: ProcessingPipelineInterface, filepath: str):

        logging.info("Video for processing: %s", filepath)

        try:
            output = pipeline.process(filepath)
        except Exception as err:
            return {"error": err.args}, 500

        return output, 200

