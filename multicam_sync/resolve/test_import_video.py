"""模块 1 的离线单元测试，不需要启动 DaVinci Resolve。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from resolve.import_video import import_videos


class FakeClip:
    def __init__(self, path: str):
        self.path = path
        self.metadata: dict[str, str] = {}

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
    def __init__(self):
        self.root = FakeFolder("Master")
        self.root.subfolders = []
        self.folders: list[FakeFolder] = []
        self.current_folder = self.root

    def GetRootFolder(self):
        return self.root

    def AddSubFolder(self, _parent, name: str):
        if any(folder.GetName() == name for folder in self.folders):
            return None
        folder = FakeFolder(name)
        self.folders.append(folder)
        self.root.subfolders.append(folder)
        return folder

    def SetCurrentFolder(self, folder):
        self.current_folder = folder
        return True

    def ImportMedia(self, paths):
        clips = [FakeClip(path) for path in paths]
        self.current_folder.clips.extend(clips)
        return clips


class FakeProject:
    def __init__(self):
        self.media_pool = FakeMediaPool()
        self.settings = {"timelineFrameRate": "24"}

    def GetMediaPool(self):
        return self.media_pool

    def GetSetting(self, name: str):
        return self.settings.get(name, "")

    def SetSetting(self, name: str, value: str):
        self.settings[name] = str(value)
        return True


class FakeProjectManager:
    def __init__(self):
        self.projects: dict[str, FakeProject] = {}

    def LoadProject(self, name: str):
        return self.projects.get(name)

    def CreateProject(self, name: str):
        project = FakeProject()
        self.projects[name] = project
        return project


class FakeResolve:
    def __init__(self):
        self.project_manager = FakeProjectManager()

    def GetProjectManager(self):
        return self.project_manager


class ImportVideosTests(unittest.TestCase):
    def _touch(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb"):
            pass

    def test_imports_video_only_sets_camera_and_resumes_without_duplicates(self):
        with tempfile.TemporaryDirectory() as source_dir:
            self._touch(os.path.join(source_dir, "视频", "A机", "卡1", "M4ROOT", "CLIP", "A001.MP4"))
            self._touch(os.path.join(source_dir, "视频", "A机", "卡2", "M4ROOT", "CLIP", "A002.mov"))
            self._touch(os.path.join(source_dir, "视频", "B机", "M4ROOT", "CLIP", "B001.MXF"))
            self._touch(os.path.join(source_dir, "视频", "action", "DCIM", "skip.mp4"))
            self._touch(os.path.join(source_dir, "音频", "sound.wav"))
            resolve = FakeResolve()

            first = import_videos(source_dir, resolve=resolve)
            second = import_videos(source_dir, resolve=resolve)

            self.assertEqual(first.expected_count, 3)
            self.assertEqual(first.imported_count, 3)
            self.assertEqual(second.imported_count, 0)
            self.assertEqual(second.existing_count, 3)
            self.assertEqual(first.timeline_fps, 50)

            project = resolve.GetProjectManager().LoadProject(os.path.basename(source_dir))
            clips = project.GetMediaPool().current_folder.GetClipList()
            self.assertEqual([clip.GetMetadata("Camera #") for clip in clips], ["a", "a", "b"])
            self.assertTrue(all("Camera" not in clip.metadata for clip in clips))

            with open(os.path.join(source_dir, ".pipeline_state.json"), encoding="utf-8") as state_file:
                state = json.load(state_file)
            self.assertIn("RESOLVE_IMPORT_VIDEO", state["completed_steps"])

    def test_direct_card_layout_groups_subcards_and_uses_custom_project_name(self):
        with tempfile.TemporaryDirectory() as source_dir:
            self._touch(os.path.join(source_dir, "A1", "M4ROOT", "CLIP", "A001.MP4"))
            self._touch(os.path.join(source_dir, "A1", "M4ROOT", "CLIP", "._A001.MP4"))
            self._touch(os.path.join(source_dir, "A2", "M4ROOT", "CLIP", "A002.MOV"))
            self._touch(os.path.join(source_dir, "C3", "M4ROOT", "CLIP", "C001.MP4"))
            self._touch(os.path.join(source_dir, "A3", "XDROOT", "Clip", "skip.MXF"))
            self._touch(os.path.join(source_dir, "航拍", "DCIM", "skip.mp4"))
            self._touch(os.path.join(source_dir, "录音", "take.wav"))
            resolve = FakeResolve()

            result = import_videos(
                source_dir,
                project_name="测试工程",
                resolve=resolve,
            )

            self.assertEqual(result.project_name, "测试工程")
            self.assertEqual(result.expected_count, 3)
            project = resolve.GetProjectManager().LoadProject("测试工程")
            folder = project.GetMediaPool().current_folder
            self.assertEqual(folder.GetName(), os.path.basename(source_dir))
            self.assertEqual(
                [clip.GetMetadata("Camera #") for clip in folder.GetClipList()],
                ["a", "a", "c"],
            )
            self.assertEqual(project.GetSetting("timelineFrameRate"), "50")

    def test_creates_project_with_requested_frame_rate(self):
        with tempfile.TemporaryDirectory() as source_dir:
            self._touch(os.path.join(source_dir, "视频", "A机", "M4ROOT", "CLIP", "A001.MP4"))
            resolve = FakeResolve()

            result = import_videos(source_dir, fps=25, resolve=resolve)

            self.assertEqual(result.timeline_fps, 25)
            project = resolve.GetProjectManager().LoadProject(os.path.basename(source_dir))
            self.assertEqual(project.GetSetting("timelineFrameRate"), "25")


if __name__ == "__main__":
    unittest.main()
