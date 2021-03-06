# Copyright (c) 2018 PaddlePaddle Authors. All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import time
import six
import numpy as np
import math
import argparse
import logging
import paddle.fluid as fluid
import paddle
import time
import reader as reader
from nets import MultiviewSimnet, SimpleEncoderFactory

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("fluid")
logger.setLevel(logging.INFO)


def parse_args():
    parser = argparse.ArgumentParser("multi-view simnet")
    parser.add_argument("--train_file", type=str, help="Training file")
    parser.add_argument("--valid_file", type=str, help="Validation file")
    parser.add_argument(
        "--epochs", type=int, default=10, help="Number of epochs for training")
    parser.add_argument(
        "--model_output_dir",
        type=str,
        default='model_output',
        help="Model output folder")
    parser.add_argument(
        "--query_slots", type=int, default=1, help="Number of query slots")
    parser.add_argument(
        "--title_slots", type=int, default=1, help="Number of title slots")
    parser.add_argument(
        "--query_encoder",
        type=str,
        default="bow",
        help="Encoder module for slot encoding")
    parser.add_argument(
        "--title_encoder",
        type=str,
        default="bow",
        help="Encoder module for slot encoding")
    parser.add_argument(
        "--query_encode_dim",
        type=int,
        default=128,
        help="Dimension of query encoder output")
    parser.add_argument(
        "--title_encode_dim",
        type=int,
        default=128,
        help="Dimension of title encoder output")
    parser.add_argument(
        "--batch_size", type=int, default=128, help="Batch size for training")
    parser.add_argument(
        "--embedding_dim",
        type=int,
        default=128,
        help="Default Dimension of Embedding")
    parser.add_argument(
        "--sparse_feature_dim",
        type=int,
        default=1000001,
        help="Sparse feature hashing space"
        "for index processing")
    parser.add_argument(
        "--hidden_size", type=int, default=128, help="Hidden dim")
    return parser.parse_args()


def start_train(args):
    dataset = reader.SyntheticDataset(args.sparse_feature_dim, args.query_slots,
                                      args.title_slots)
    train_reader = paddle.batch(
        paddle.reader.shuffle(
            dataset.train(), buf_size=args.batch_size * 100),
        batch_size=args.batch_size)
    place = fluid.CPUPlace()
    factory = SimpleEncoderFactory()
    query_encoders = [
        factory.create(args.query_encoder, args.query_encode_dim)
        for i in range(args.query_slots)
    ]
    title_encoders = [
        factory.create(args.title_encoder, args.title_encode_dim)
        for i in range(args.title_slots)
    ]
    m_simnet = MultiviewSimnet(args.sparse_feature_dim, args.embedding_dim,
                               args.hidden_size)
    m_simnet.set_query_encoder(query_encoders)
    m_simnet.set_title_encoder(title_encoders)
    all_slots, avg_cost, correct = m_simnet.train_net()
    optimizer = fluid.optimizer.Adam(learning_rate=1e-4)
    optimizer.minimize(avg_cost)
    startup_program = fluid.default_startup_program()
    loop_program = fluid.default_main_program()

    feeder = fluid.DataFeeder(feed_list=all_slots, place=place)
    exe = fluid.Executor(place)
    exe.run(startup_program)

    for pass_id in range(args.epochs):
        for batch_id, data in enumerate(train_reader()):
            loss_val, correct_val = exe.run(loop_program,
                                            feed=feeder.feed(data),
                                            fetch_list=[avg_cost, correct])
            logger.info("TRAIN --> pass: {} batch_id: {} avg_cost: {}, acc: {}"
                        .format(pass_id, batch_id, loss_val,
                                float(correct_val) / args.batch_size))
        fluid.io.save_inference_model(args.model_output_dir,
                                      [val.name for val in all_slots],
                                      [avg_cost, correct], exe)


def main():
    args = parse_args()
    start_train(args)


if __name__ == "__main__":
    main()
