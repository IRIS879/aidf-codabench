import json
import uuid
from datetime import timedelta, date
from io import BytesIO
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers

from api.serializers.submissions import SubmissionCreationSerializer, extract_model_card_metadata
from api.serializers.competitions import CompetitionSerializer
from competitions.models import Submission
from competitions.tasks import run_submission, submission_status_cleanup

from factories import SubmissionFactory, UserFactory, CompetitionFactory, PhaseFactory, TaskFactory, LeaderboardFactory
from leaderboards.models import Leaderboard


class SubmissionTestCase(TestCase):
    def setUp(self):
        self.user = UserFactory(username='test')
        self.competition = CompetitionFactory(created_by=self.user)
        self.phase = PhaseFactory(competition=self.competition)

    def make_submission(self, **kwargs):
        kwargs.setdefault('owner', self.user)
        kwargs.setdefault('phase', self.phase)
        kwargs.setdefault('created_when', timezone.now())
        return SubmissionFactory(**kwargs)


class MaxSubmissionsTests(SubmissionTestCase):
    def set_max_submissions(self, phase=None, per_person=None, per_day=None):
        phase = self.phase if phase is None else phase
        phase.has_max_submissions = True
        phase.max_submissions_per_person = per_person
        phase.max_submissions_per_day = per_day
        phase.save()

    def test_creating_submission_checks_max_submission_per_day_not_exceeded(self):
        self.set_max_submissions(per_day=1)
        self.make_submission()
        self.assertRaises(PermissionError, self.make_submission)

    def test_creating_submission_checks_max_submission_per_person_not_exceeded(self):
        self.set_max_submissions(per_person=1)
        self.make_submission()
        self.assertRaises(PermissionError, self.make_submission)

    def test_failed_submissions_not_counted_towards_max(self):
        self.set_max_submissions(per_person=1, per_day=1)
        self.make_submission(status="Failed")
        try:
            self.make_submission()
        except PermissionError:
            assert False, "This counted failed submissions"

    def test_max_per_day_not_counting_previous_days_submissions(self):
        self.set_max_submissions(per_day=1)
        yesterday = timezone.now() - timedelta(days=1)
        self.make_submission(created_when=yesterday)
        try:
            self.make_submission()
        except PermissionError:
            assert False, "This counted yesterday's submissions"

    def test_max_submissions_not_counting_other_user_submissions(self):
        self.set_max_submissions(per_person=1, per_day=1)
        other_user = UserFactory()
        self.make_submission(owner=other_user)
        try:
            self.make_submission()
        except PermissionError:
            assert False, "This counted other user's submissions"

    def test_submission_not_created_if_max_reached(self):
        self.set_max_submissions(per_person=1)
        self.make_submission()
        self.assertRaises(PermissionError, self.make_submission)
        assert not Submission.objects.filter(name='Find Me').exists()

    def test_children_submissions_dont_count_toward_max(self):
        self.make_submission(parent=self.make_submission())
        self.set_max_submissions(per_person=2)
        self.make_submission()
        self.assertRaises(PermissionError, self.make_submission)


class SubmissionManagerTests(SubmissionTestCase):
    def test_re_run_submission_creates_new_submission_with_same_data_owner_and_phase(self):
        sub = self.make_submission()
        with mock.patch('competitions.tasks._send_to_compute_worker'):
            sub.start()
            assert Submission.objects.all().count() == 1
            sub.re_run()
        assert Submission.objects.all().count() == 2
        subs = Submission.objects.all()
        assert subs[0].owner == subs[1].owner
        assert subs[0].phase == subs[1].phase
        assert subs[0].data == subs[1].data

    def test_cancel_submission_sets_status(self):
        sub = self.make_submission()
        assert sub.cancel(), 'Cancel returned False, meaning the submission could not be cancelled when it should'
        assert sub.status == 'Cancelled'
        assert sub.status == 'Cancelled'

    def test_cancel_does_nothing_if_status_is_cancelled_failed_or_finished(self):
        sub = self.make_submission()
        for status in ['Failed', 'Cancelled', 'Finished']:
            sub.status = status
            assert not sub.cancel(), "Cancel returned True, meaning submission could be cancelled when it shouldn\'t"
            assert sub.status == status, 'Status was changed and should not have been'

    def test_adding_submission_to_leaderboard_adds_all_children(self):
        parent_sub = SubmissionFactory(has_children=True)
        leaderboard = LeaderboardFactory()
        parent_sub.phase.leaderboard = leaderboard
        parent_sub.phase.save()

        for _ in range(10):
            SubmissionFactory(parent=parent_sub)

        self.client.force_login(parent_sub.owner)
        url = reverse('submission-submission-leaderboard-connection', kwargs={'pk': parent_sub.pk})
        resp = self.client.post(url)
        assert resp.status_code == 200
        for submission in Submission.objects.filter(parent=parent_sub):
            assert submission.leaderboard

    def test_remove_submission_from_leaderboard(self):
        parent_sub = SubmissionFactory(has_children=True)
        leaderboard = LeaderboardFactory(submission_rule=Leaderboard.ADD_DELETE)
        parent_sub.phase.leaderboard = leaderboard
        parent_sub.phase.save()

        for _ in range(10):
            SubmissionFactory(parent=parent_sub)

        self.client.force_login(parent_sub.owner)
        url = reverse('submission-submission-leaderboard-connection', kwargs={'pk': parent_sub.pk})
        self.client.post(url)
        resp = self.client.delete(url)
        assert resp.status_code == 200
        for submission in Submission.objects.filter(parent=parent_sub):
            assert submission.leaderboard is None

    def test_only_owner_can_add_submission_to_leaderboard(self):
        parent_sub = SubmissionFactory(has_children=True)
        leaderboard = LeaderboardFactory()
        parent_sub.phase.leaderboard = leaderboard
        parent_sub.phase.save()

        different_user = UserFactory()
        self.client.force_login(different_user)
        url = reverse('submission-submission-leaderboard-connection', kwargs={'pk': parent_sub.pk})
        resp = self.client.post(url)
        assert resp.status_code == 403
        assert resp.data["detail"] == "You cannot perform this action, contact the competition organizer!"

    def test_only_owner_can_remove_submission_from_leaderboard(self):
        parent_sub = SubmissionFactory(has_children=True)
        leaderboard = LeaderboardFactory()
        parent_sub.phase.leaderboard = leaderboard
        parent_sub.phase.save()

        different_user = UserFactory()
        self.client.force_login(different_user)
        url = reverse('submission-submission-leaderboard-connection', kwargs={'pk': parent_sub.pk})
        resp = self.client.delete(url)
        assert resp.status_code == 403
        assert resp.data["detail"] == "You cannot perform this action, contact the competition organizer!"

    def test_adding_submission_removes_other_submissions_from_owner(self):
        leaderboard = LeaderboardFactory()
        phase = PhaseFactory(leaderboard=leaderboard)
        user = UserFactory()
        first_parent_sub = SubmissionFactory(has_children=True, phase=phase, owner=user)
        second_parent_sub = SubmissionFactory(has_children=True, phase=phase, owner=user)

        for _ in range(10):
            SubmissionFactory(parent=first_parent_sub, owner=user, phase=phase)
            SubmissionFactory(parent=second_parent_sub, owner=user, phase=phase)

        self.client.force_login(user)
        url = reverse('submission-submission-leaderboard-connection', kwargs={'pk': first_parent_sub.pk})
        resp = self.client.post(url)
        assert resp.status_code == 200
        url = reverse('submission-submission-leaderboard-connection', kwargs={'pk': second_parent_sub.pk})
        resp = self.client.post(url)
        assert resp.status_code == 200
        for submission in Submission.objects.filter(parent=first_parent_sub):
            assert submission.leaderboard is None
        for submission in Submission.objects.filter(parent=second_parent_sub):
            assert submission.leaderboard == leaderboard

    def test_adding_multiple_submissions_to_leaderboard(self):
        leaderboard = LeaderboardFactory(submission_rule=Leaderboard.ADD_DELETE_MULTIPLE)
        phase = PhaseFactory(leaderboard=leaderboard)
        user = UserFactory()
        first_parent_sub = SubmissionFactory(has_children=True, phase=phase, owner=user)
        second_parent_sub = SubmissionFactory(has_children=True, phase=phase, owner=user)

        for _ in range(10):
            SubmissionFactory(parent=first_parent_sub, phase=phase, owner=user)
            SubmissionFactory(parent=second_parent_sub, phase=phase, owner=user)

        self.client.force_login(user)
        url = reverse('submission-submission-leaderboard-connection', kwargs={'pk': first_parent_sub.pk})
        resp = self.client.post(url)
        assert resp.status_code == 200
        url = reverse('submission-submission-leaderboard-connection', kwargs={'pk': second_parent_sub.pk})
        resp = self.client.post(url)
        assert resp.status_code == 200
        for submission in Submission.objects.filter(parent=first_parent_sub):
            assert submission.leaderboard == leaderboard
        for submission in Submission.objects.filter(parent=second_parent_sub):
            assert submission.leaderboard == leaderboard

    def test_cannot_add_task_specific_submission_to_leaderboard(self):
        sub = SubmissionFactory(is_specific_task_re_run=True)
        leaderboard = LeaderboardFactory()
        sub.phase.leaderboard = leaderboard
        sub.phase.save()

        self.client.force_login(sub.owner)
        url = reverse('submission-submission-leaderboard-connection', kwargs={'pk': sub.pk})
        resp = self.client.post(url)
        assert resp.status_code == 403


class MultipleTasksPerPhaseTests(SubmissionTestCase):
    def setUp(self):
        self.user = UserFactory()
        self.comp = CompetitionFactory()
        self.tasks = [TaskFactory() for _ in range(2)]
        self.phase = PhaseFactory(competition=self.comp, tasks=self.tasks)

    def mock_run_submission(self, submission, task=None):
        with mock.patch('competitions.tasks.app.send_task') as celery_app:
            with mock.patch('competitions.tasks.make_url_sassy') as mock_sassy:
                class Task:
                    def __init__(self):
                        self.id = uuid.uuid4()

                if task is None:
                    task = Task()
                celery_app.return_value = task
                mock_sassy.return_value = ''
                run_submission(submission.pk)
                return celery_app

    def test_making_submission_creates_parent_sub_and_additional_sub_per_task(self):
        self.sub = self.make_submission()
        with mock.patch('competitions.tasks.send_parent_status'):
            with mock.patch('competitions.tasks.send_child_id'):
                resp = self.mock_run_submission(self.sub)
        assert resp.call_count == 2
        sub = Submission.objects.get(id=self.sub.id)
        assert sub.has_children
        assert sub.children.count() == 2

    def test_children_always_created_in_the_same_order(self):
        self.sub = self.make_submission()
        with mock.patch('competitions.tasks.send_parent_status'):
            with mock.patch('competitions.tasks.send_child_id'):
                resp = self.mock_run_submission(self.sub)
        assert resp.call_count == 2

        self.sub = Submission.objects.get(id=self.sub.id)
        children = self.sub.children.order_by('id').values_list('id', flat=True)
        first_call_args = resp.call_args_list[0][1]['args'][0]
        second_call_args = resp.call_args_list[1][1]['args'][0]
        assert first_call_args['id'] == children[0]
        assert second_call_args['id'] == children[1]

    def test_making_submission_to_phase_with_one_task_does_not_create_parents_or_children(self):
        self.single_phase = PhaseFactory(competition=self.comp)
        self.sub = self.make_submission(phase=self.single_phase)
        resp = self.mock_run_submission(self.sub)
        assert resp.call_count == 1
        sub = Submission.objects.get(id=self.sub.id)
        assert not sub.has_children

    def test_adding_task_to_phase_runs_submissions_on_new_task(self):
        leaderboard = LeaderboardFactory()
        self.comp.phases.all().update(leaderboard=leaderboard)
        SubmissionFactory(owner=self.user, phase=self.phase)
        competition_data = CompetitionSerializer(self.comp).data
        new_task = TaskFactory()
        competition_data["phases"][0]['tasks'].append(new_task.key)
        competition_data['logo'] = None

        for task_index, task in enumerate(competition_data["phases"][0]['tasks']):
            competition_data["phases"][0]['tasks'][task_index] = str(task)
        url = reverse("competition-detail", args=(self.comp.pk,))

        self.client.force_login(self.comp.created_by)

        # during our put we should expect 1 new run to happen
        with mock.patch('api.views.competitions.CompetitionViewSet.run_new_task_submissions') as run_new_task_submission:
            self.client.put(url, json.dumps(competition_data), content_type="application/json")
            run_new_task_submission.assert_called_once()

    def test_static_competition_routes_to_static_queue(self):
        self.comp.training_mode = 'static'
        self.comp.static_split_column = 'yyyy'
        self.comp.static_split_value = '2022'
        self.comp.save()
        single_phase = PhaseFactory(competition=self.comp)
        submission = self.make_submission(phase=single_phase)
        with mock.patch('competitions.tasks.app.send_task') as celery_app:
            with mock.patch('competitions.tasks.make_url_sassy') as mock_sassy:
                class Task:
                    def __init__(self):
                        self.id = uuid.uuid4()

                celery_app.return_value = Task()
                mock_sassy.return_value = ''
                run_submission(submission.pk)
                assert celery_app.call_args[1]['queue'] == 'compute-worker-static'
                assert celery_app.call_args[1]['args'][0]['training_mode'] == 'static'
                assert celery_app.call_args[1]['args'][0]['static_split_column'] == 'yyyy'
                assert celery_app.call_args[1]['args'][0]['static_split_value'] == '2022'

    def test_rolling_competition_routes_to_rolling_queue(self):
        self.comp.training_mode = 'rolling'
        self.comp.period_col = 'yyyy'
        self.comp.rolling_start_period = '2018'
        self.comp.rolling_end_period = '2019'
        self.comp.rolling_window_size = 2
        self.comp.rolling_window_start_date = date(2018, 1, 1)
        self.comp.rolling_window_end_date = date(2019, 1, 1)
        self.comp.save()
        single_phase = PhaseFactory(competition=self.comp)
        submission = self.make_submission(phase=single_phase)
        with mock.patch('competitions.tasks.app.send_task') as celery_app:
            with mock.patch('competitions.tasks.make_url_sassy') as mock_sassy:
                class Task:
                    def __init__(self):
                        self.id = uuid.uuid4()

                celery_app.return_value = Task()
                mock_sassy.return_value = ''
                run_submission(submission.pk)
                assert celery_app.call_args[1]['queue'] == 'compute-worker-rolling'
                assert celery_app.call_args[1]['args'][0]['training_mode'] == 'rolling'
                assert celery_app.call_args[1]['args'][0]['period_col'] == 'yyyy'
                assert celery_app.call_args[1]['args'][0]['rolling_start_period'] == '2018'
                assert celery_app.call_args[1]['args'][0]['rolling_end_period'] == '2019'


class FactSheetTests(SubmissionTestCase):
    def setUp(self):
        super().setUp()
        self.competition.fact_sheet = {
            "boolean": {
                "key": "boolean",
                "type": "checkbox",
                "title": "boolean",
                "selection": [True, False],
                "is_required": "false",
                "is_on_leaderboard": "false"
            },
            "text": {
                "key": "text",
                "type": "text",
                "title": "text",
                "selection": "",
                "is_required": "false",
                "is_on_leaderboard": "false"
            },
            "text_required": {
                "key": "text_required",
                "type": "text",
                "title": "text",
                "selection": "",
                "is_required": "true",
                "is_on_leaderboard": "false"
            },
            "selection": {
                "key": "select",
                "type": "select",
                "title": "selection",
                "selection": ["", "v1", "v2", "v3"],
                "is_required": "false",
                "is_on_leaderboard": "true"
            }
        }
        self.competition.save()

    def test_fact_sheet_valid(self):
        submission = SubmissionCreationSerializer(super().make_submission()).data
        submission['fact_sheet_answers'] = {
            "boolean": True,
            "selection": "v3",
            "text_required": "accept_text",
            "text": "",
        }
        serializer = SubmissionCreationSerializer(data=submission, instance=Submission)
        assert serializer.is_valid(raise_exception=True)

    def test_fact_sheet_with_extra_keys_is_not_valid(self):
        submission = SubmissionCreationSerializer(super().make_submission()).data
        submission['fact_sheet_answers'] = {
            "boolean": True,
            "selection": "value3",
            "text_required": "accept_text",
            "text": "accept any",
            "extrakey": True,
            "extrakey2": "NotInFactSheet",
        }
        serializer = SubmissionCreationSerializer(data=submission, instance=Submission)
        assert not serializer.is_valid()

    def test_fact_sheet_with_missing_key_is_not_valid(self):
        submission = SubmissionCreationSerializer(super().make_submission()).data
        submission['fact_sheet_answers'] = {
            "boolean": True,
            "selection": "value3",
        }
        serializer = SubmissionCreationSerializer(data=submission, instance=Submission)
        assert not serializer.is_valid()

    def test_fact_sheet_with_wrong_selection_is_not_valid(self):
        submission = SubmissionCreationSerializer(super().make_submission()).data
        submission['fact_sheet_answers'] = {
            "boolean": True,
            "selection": "new_value",
            "text": "accept any",
        }
        serializer = SubmissionCreationSerializer(data=submission, instance=Submission)
        assert not serializer.is_valid()

    def test_fact_sheet_with_blank_required_text_is_not_valid(self):
        submission = SubmissionCreationSerializer(super().make_submission()).data
        submission['fact_sheet_answers'] = {
            "boolean": True,
            "selection": "v3",
            "text_required": "",
            "text": "",
        }
        serializer = SubmissionCreationSerializer(data=submission, instance=Submission)
        assert not serializer.is_valid()

    def test_edit_fact_sheet_endpoint(self):
        submission = super().make_submission()
        self.client.login(username=self.user.username, password=self.user.password)
        url = reverse('submission-update-fact-sheet', args=[submission.id])
        data = {
            "boolean": True,
            "selection": "v3",
            "text_required": "accept_text",
            "text": "",
        }
        data = json.dumps(data)
        resp = self.client.patch(url, data, content_type='application/json')
        assert resp.status_code == 200
        submission.refresh_from_db()
        assert json.loads(data) == submission.fact_sheet_answers


class ModelCardParsingTests(TestCase):
    def make_pdf_file(self):
        pdf_file = BytesIO(b"%PDF-1.4 mock")
        pdf_file.name = "model_card.pdf"
        pdf_file.content_type = "application/pdf"
        return pdf_file

    def mock_reader(self, text):
        page = mock.Mock()
        page.extract_text.return_value = text
        reader = mock.Mock()
        reader.pages = [page]
        return reader

    def test_extract_model_card_metadata_rejects_incomplete_template(self):
        mock_pdf_reader = mock.Mock(return_value=self.mock_reader(
            """
            Model Card
            Model Information
            Model Name:
            Task: Classification
            Output: Label

            Overview
            Briefly describe the purpose of the model and the problem it is designed to solve.
            """
        ))

        with mock.patch.dict("sys.modules", {"pypdf": mock.Mock(PdfReader=mock_pdf_reader)}):
            model_name, parsed_json = extract_model_card_metadata(self.make_pdf_file())

        assert model_name is None
        assert parsed_json is None

    def test_extract_model_card_metadata_requires_task_and_output(self):
        mock_pdf_reader = mock.Mock(return_value=self.mock_reader(
            """
            Model Card

            Model Information
            Model Name: Baseline Model
            Task:
            Output:

            Overview
            This model predicts labels for the benchmark task.
            """
        ))

        with mock.patch.dict("sys.modules", {"pypdf": mock.Mock(PdfReader=mock_pdf_reader)}):
            model_name, parsed_json = extract_model_card_metadata(self.make_pdf_file())

        assert model_name is None
        assert parsed_json is None

    def test_extract_model_card_metadata_does_not_use_task_output_as_model_name(self):
        mock_pdf_reader = mock.Mock(return_value=self.mock_reader(
            """
            Model Card

            Model Information

            Model Name:
            Task:
            Output:

            Overview
            Briefly describe the purpose of the model and the problem it is designed to solve.
            """
        ))

        with mock.patch.dict("sys.modules", {"pypdf": mock.Mock(PdfReader=mock_pdf_reader)}):
            model_name, parsed_json = extract_model_card_metadata(self.make_pdf_file())

        assert model_name is None
        assert parsed_json is None

    def test_extract_model_card_metadata_rejects_overview_prompt_without_added_content(self):
        mock_pdf_reader = mock.Mock(return_value=self.mock_reader(
            """
            Model Card
            Model Information
            Model Name: Baseline Model
            Task: Classification
            Output: Label

            Overview
            Briefly describe the purpose of the model and the problem it is designed to solve.
            """
        ))

        with mock.patch.dict("sys.modules", {"pypdf": mock.Mock(PdfReader=mock_pdf_reader)}):
            model_name, parsed_json = extract_model_card_metadata(self.make_pdf_file())

        assert model_name is None
        assert parsed_json is None

    def test_extract_model_card_metadata_accepts_filled_required_sections(self):
        mock_pdf_reader = mock.Mock(return_value=self.mock_reader(
            """
            Model Card
            Model Information
            Model Name: Baseline Model
            Task: Classification
            Output: Label

            Overview
            Briefly describe the purpose of the model and the problem it is designed to solve.
            This model predicts labels for the benchmark task.
            """
        ))

        with mock.patch.dict("sys.modules", {"pypdf": mock.Mock(PdfReader=mock_pdf_reader)}):
            model_name, parsed_json = extract_model_card_metadata(self.make_pdf_file())

        assert model_name == "Baseline Model"
        assert parsed_json["model_name"] == "Baseline Model"
        assert parsed_json["task"] == "Classification"
        assert parsed_json["output"] == "Label"
        assert parsed_json["overview"] == "This model predicts labels for the benchmark task."

    def test_extract_model_card_metadata_accepts_overview_without_template_prompt(self):
        mock_pdf_reader = mock.Mock(return_value=self.mock_reader(
            """
            Model Card
            Model Information
            Model Name: Baseline Model
            Task: Classification
            Output: Label

            Overview
            This model predicts labels for the benchmark task.
            """
        ))

        with mock.patch.dict("sys.modules", {"pypdf": mock.Mock(PdfReader=mock_pdf_reader)}):
            model_name, parsed_json = extract_model_card_metadata(self.make_pdf_file())

        assert model_name == "Baseline Model"
        assert parsed_json["overview"] == "This model predicts labels for the benchmark task."

    def test_extract_model_card_metadata_accepts_single_line_model_information_extraction(self):
        mock_pdf_reader = mock.Mock(return_value=self.mock_reader(
            """
            Model Card  Model Information Model Name: test model name Task: test task Output: test output
            Overview Briefly describe the purpose of the model and the problem it is designed to solve. test overview
            Data
            """
        ))

        with mock.patch.dict("sys.modules", {"pypdf": mock.Mock(PdfReader=mock_pdf_reader)}):
            model_name, parsed_json = extract_model_card_metadata(self.make_pdf_file())

        assert model_name == "test model name"
        assert parsed_json["model_name"] == "test model name"
        assert parsed_json["task"] == "test task"
        assert parsed_json["output"] == "test output"
        assert parsed_json["overview"] == "test overview"
        assert len(parsed_json["model_name"]) < 120
        assert parsed_json["model_name"] == "test model name"

    def test_serializer_model_card_validation_uses_field_error(self):
        serializer = SubmissionCreationSerializer()
        mock_pdf_reader = mock.Mock(return_value=self.mock_reader(
            """
            Model Card
            Model Information
            Model Name:
            Task: Classification
            Output: Label

            Overview
            """
        ))

        with mock.patch.dict("sys.modules", {"pypdf": mock.Mock(PdfReader=mock_pdf_reader)}):
            with self.assertRaises(serializers.ValidationError) as exc:
                serializer._validate_model_card_pdf(self.make_pdf_file())

        assert "model_card_file" in exc.exception.detail
        assert "Model card parsing failed" in str(exc.exception.detail["model_card_file"][0])


class TestSubmissionTasks(SubmissionTestCase):
    def test_submissions_are_cancelled_if_running_24_hours_past_execution_time_limit(self):
        self.submission_fail, self.submission_pass = self.make_submission(), self.make_submission()
        self.submission_fail.status = self.submission_pass.status = Submission.RUNNING
        self.submission_fail.started_when = timezone.now() - timedelta(milliseconds=(3600000 * 24) + self.submission_fail.phase.execution_time_limit)
        self.submission_fail.save()
        self.submission_pass.save()
        submission_status_cleanup()
        self.submission_fail.refresh_from_db()
        self.submission_pass.refresh_from_db()
        assert self.submission_pass.status == Submission.RUNNING
        assert self.submission_fail.status == Submission.FAILED

    def test_cancelling_parent_submission_cancels_all_children(self):
        self.parent_submission = self.make_submission()
        self.parent_submission.has_children = True
        self.parent_submission.save()
        for i in range(2):
            sub = self.make_submission()
            sub.parent = self.parent_submission
            sub.save()

        assert self.parent_submission.status != Submission.FAILED
        for sub in self.parent_submission.children.all():
            assert sub.status != Submission.FAILED

        self.parent_submission.cancel(status=Submission.FAILED)
        self.parent_submission.refresh_from_db()

        assert self.parent_submission.status == Submission.FAILED
        for sub in self.parent_submission.children.all():
            assert sub.status == Submission.FAILED
