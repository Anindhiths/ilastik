import h5py
import numpy as np
import pytest

from ilastik.experimental.parser import PixelClassificationProject
from lazyflow.classifiers.parallelVigraRfLazyflowClassifier import (
    ParallelVigraRfLazyflowClassifier,
    ParallelVigraRfLazyflowClassifierFactory,
)

from ..types import ApiTestDataLookup, TestProjects


class TestIlastikParser:
    @pytest.mark.parametrize(
        "proj, expected_num_channels",
        [
            (TestProjects.PIXEL_CLASS_1_CHANNEL_XYC, 1),
            (TestProjects.PIXEL_CLASS_3_CHANNEL, 3),
        ],
    )
    def test_parse_project_number_of_channels(self, test_data_lookup: ApiTestDataLookup, proj, expected_num_channels):
        project_path = test_data_lookup.find_project(proj)
        with h5py.File(project_path, "r") as f:
            proj = PixelClassificationProject.model_validate(f)

        assert proj.input_data.num_channels == expected_num_channels

    @pytest.mark.parametrize(
        "proj, expected_factory, expected_classifier",
        [
            (
                TestProjects.PIXEL_CLASS_1_CHANNEL_XYC,
                ParallelVigraRfLazyflowClassifierFactory,
                ParallelVigraRfLazyflowClassifier,
            ),
        ],
    )
    def test_parse_project_classifier(self, test_data_lookup, proj, expected_factory, expected_classifier):
        project_path = test_data_lookup.find_project(proj)

        with h5py.File(project_path, "r") as f:
            proj = PixelClassificationProject.model_validate(f)

        assert isinstance(proj.classifier.classifier_factory, expected_factory)
        assert isinstance(proj.classifier.classifier, expected_classifier)

    tests = [
        (
            TestProjects.PIXEL_CLASS_1_CHANNEL_XYC,
            np.array(
                [
                    [True, False, True, False, True, False, True],
                    [False, True, False, True, False, True, False],
                    [False, True, False, True, False, True, False],
                    [False, True, False, True, False, True, False],
                    [False, False, True, False, True, False, True],
                    [False, False, True, False, True, False, True],
                ]
            ),
            np.array([True, True, True, True, True, True, True]),
        ),
        (
            TestProjects.PIXEL_CLASS_3_CHANNEL,
            np.array(
                [
                    [True, True, True, True, False, False, False],
                    [False, True, True, True, False, False, False],
                    [False, True, True, True, False, False, False],
                    [False, True, True, True, False, False, False],
                    [False, True, True, True, False, False, False],
                    [False, True, True, True, False, False, False],
                ]
            ),
            np.array([True, True, True, True, True, True, True]),
        ),
        (
            TestProjects.PIXEL_CLASS_3D_2D_3D_FEATURE_MIX,
            np.array(
                [
                    [True, False, False, False, False, True, False],
                    [False, False, False, True, False, False, False],
                    [False, False, False, True, False, False, False],
                    [False, False, False, True, False, False, False],
                    [False, False, False, False, True, False, False],
                    [False, False, False, False, True, False, False],
                ]
            ),
            np.array([False, False, False, True, False, True, False]),
        ),
    ]

    @pytest.mark.parametrize("proj, expected_sel_matrix, expected_compute_in_2d", tests)
    def test_parse_project_features(self, test_data_lookup, proj, expected_sel_matrix, expected_compute_in_2d):
        project_path = test_data_lookup.find_project(proj)

        with h5py.File(project_path, "r") as f:
            proj = PixelClassificationProject.model_validate(f)

        matrix = proj.feature_matrix
        assert matrix
        np.testing.assert_array_equal(matrix.selections, expected_sel_matrix)
        np.testing.assert_array_equal(matrix.compute_in_2d, expected_compute_in_2d)
