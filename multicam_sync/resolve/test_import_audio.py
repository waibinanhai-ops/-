"""模块 2 的离线单元测试，不需要启动 DaVinci Resolve。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from config import Step
from resolve.import_audio import import_audio
from state.manager import create_initial_state, load_state, mark_step_completed, save_state


class FakeClip:
    def __init__(self, path: str, camera: str = ""):
        self.path = path
        self.metadata = {"Camera #": camera} if camera else {}

    def GetClipProperty(self, key=None):
        if key == "File Path":
            return self.path
        return {"File Path": self.path}

    def GetMetadata(self, key: str):
        return self.metadata.get(key, "")

    def SetMetadata(self, key: str, value: str):
        self.metadata[key] = value
        return True


class FakeFolder:
    def __init__(self, name: str):
        self.name = name
        self.clips: list[FakeClip] = []

    def GetName(self):
        return self.name

    def GetClipList(self):
        return self.clips

    def GetSubFolderList(self):
        return getattr(self, "subfolders", [])


class FakeMediaPool:
    def __init__(self, date: str):
        self.root = FakeFolder("Master")
        self.date_folder = FakeFolder(date)
        self.root.subfolders = [self.date_folder]
        self.current_folder = self.date_folder

    def GetRootFolder(self):
        return self.root

    def SetCurrentFolder(self, folder):
        self.current_folder = folder
        return True

    def ImportMedia(self, paths):
        clips = [FakeClip(path, camera="device-camera") for path in paths]
        self.current_folder.clips.extend(clips)
        return clips


class FakeProject:
    def __init__(self, date: str):
        self.media_pool = FakeMediaPool(date)

    def GetMediaPool(self):
        return self.media_pool


class FakeProjectManager:
    def __init__(self, date: str):
        self.project = FakeProject(date)
        self.loaded_names: list[str] = []

    def LoadProject(self, name: str):
        self.loaded_names.append(name)
        return self.project


class FakeResolve:
    def __init__(self, date: str):
        self.project_manager = FakeProjectManager(date)

    def GetProjectManager(self):
        return self.project_manager


class ImportAudioTests(unittest.TestCase):
    def _touch(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb"):
            pass

    def _create_video_state(self, source_dir: str) -> None:
        state = create_initial_state(source_dir)
        for step in (
            Step.SCANNING,
            Step.RESOLVE_CONNECT,
            Step.RESOLVE_CREATE_PROJECT,
            Step.RESOLVE_IMPORT_VIDEO,
        ):
            mark_step_completed(state, step)
        save_state(source_dir, state)

    def test_imports_audio_clears_camera_and_resumes_without_duplicates(self):
        with tempfile.TemporaryDirectory() as source_dir:
            self._touch(os.path.join(source_dir, "视频", "A机", "M4ROOT", "CLIP", "A001.MP4"))
            self._touch(os.path.join(source_dir, "音频", "Sound", "take-01.WAV"))
            self._touch(os.path.join(source_dir, "音频", "Sound", "take-02.mp3"))
            self._create_video_state(source_dir)
            resolve = FakeResolve(os.path.basename(source_dir))

            first = import_audio(source_dir, audio_sync_confirmed=True, resolve=resolve)
            second = import_audio(source_dir, audio_sync_confirmed=True, resolve=resolve)

            self.assertEqual(first.expected_count, 2)
            self.assertEqual(first.imported_count, 2)
            self.assertEqual(first.cleared_camera_count, 2)
            self.assertEqual(second.imported_count, 0)
            self.assertEqual(second.existing_count, 2)
            clips = resolve.GetProjectManager().project.GetMediaPool().date_folder.GetClipList()
            self.assertEqual([clip.GetMetadata("Camera #") for clip in clips], ["", ""])

            with open(os.path.join(source_dir, ".pipeline_state.json"), encoding="utf-8") as state_file:
                state = json.load(state_file)
            self.assertIn(Step.RESOLVE_AUDIO_SYNC, state["completed_steps"])
            self.assertIn(Step.RESOLVE_IMPORT_AUDIO, state["completed_steps"])
            self.assertEqual(state["current_step"], Step.RESOLVE_CREATE_MULTICAM)

    def test_loads_custom_project_name_recorded_by_video_import(self):
        with tempfile.TemporaryDirectory() as source_dir:
            self._touch(os.path.join(source_dir, "视频", "A机", "M4ROOT", "CLIP", "A001.MP4"))
            self._touch(os.path.join(source_dir, "音频", "take-01.WAV"))
            self._create_video_state(source_dir)
            state = load_state(source_dir)
            assert state is not None
            state["resolve"]["project_name"] = "测试工程"
            save_state(source_dir, state)
            resolve = FakeResolve(os.path.basename(source_dir))

            import_audio(source_dir, audio_sync_confirmed=True, resolve=resolve)

            self.assertEqual(resolve.GetProjectManager().loaded_names[-1], "测试工程")


if __name__ == "__main__":
    unittest.main()
