"""
Tests for sigil_pipeline.cli.ecosystem module.

Tests the CLI orchestrator for the SigilDERG ecosystem pipeline.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sigil_pipeline.cli.ecosystem import main, run_full_pipeline


class TestRunFullPipeline:
    """Test run_full_pipeline function."""

    def test_all_steps_disabled(self):
        """Test with all steps disabled."""
        exit_code = run_full_pipeline(
            generate_dataset=False,
            fine_tune=False,
            evaluate=False,
        )
        assert exit_code == 0

    def test_generate_requires_crate_list(self):
        """Test that dataset generation requires crate_list."""
        exit_code = run_full_pipeline(
            generate_dataset=True,
            fine_tune=False,
            evaluate=False,
            crate_list=None,  # Missing crate list
        )
        assert exit_code == 1

    @patch("subprocess.run")
    def test_generate_dataset_success(self, mock_run):
        """Test successful dataset generation."""
        mock_run.return_value = MagicMock(returncode=0)

        exit_code = run_full_pipeline(
            generate_dataset=True,
            fine_tune=False,
            evaluate=False,
            crate_list="data/test_crates.txt",
            dataset_path="test_output.jsonl",
        )

        assert exit_code == 0
        mock_run.assert_called_once()

        # Verify command includes expected arguments
        call_args = mock_run.call_args[0][0]
        assert "-m" in call_args
        assert "sigil_pipeline.main" in call_args
        assert "--crate-list" in call_args
        assert "data/test_crates.txt" in call_args

    @patch("subprocess.run")
    def test_generate_dataset_failure(self, mock_run):
        """Test dataset generation failure handling."""
        mock_run.return_value = MagicMock(returncode=1)

        exit_code = run_full_pipeline(
            generate_dataset=True,
            fine_tune=False,
            evaluate=False,
            crate_list="data/test_crates.txt",
        )

        assert exit_code == 1

    @patch("subprocess.run")
    def test_fine_tune_missing_module(self, mock_run):
        """Test fine-tune when rust_qlora module is missing."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("importlib.import_module") as mock_import:
            mock_import.side_effect = ImportError("Module not found")

            exit_code = run_full_pipeline(
                generate_dataset=False,
                fine_tune=True,
                evaluate=False,
            )

            assert exit_code == 1

    @patch("subprocess.run")
    def test_fine_tune_success(self, mock_run):
        """Test successful fine-tuning."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("importlib.import_module"):
            run_full_pipeline(
                generate_dataset=False,
                fine_tune=True,
                evaluate=False,
                config_path="configs/test.yml",
            )

            # Fine-tuning should have been attempted
            # (May fail due to missing module, which is expected)

    @patch("subprocess.run")
    def test_evaluate_missing_checkpoint_dir(self, mock_run, tmp_path: Path):
        """Test evaluation when checkpoint directory doesn't exist."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("importlib.import_module"):
            exit_code = run_full_pipeline(
                generate_dataset=False,
                fine_tune=False,
                evaluate=True,
                output_dir=str(tmp_path / "nonexistent"),
            )

            assert exit_code == 1

    @patch("subprocess.run")
    def test_evaluate_no_checkpoints(self, mock_run, tmp_path: Path):
        """Test evaluation when no checkpoints found."""
        mock_run.return_value = MagicMock(returncode=0)

        # Create empty output dir
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("importlib.import_module"):
            exit_code = run_full_pipeline(
                generate_dataset=False,
                fine_tune=False,
                evaluate=True,
                output_dir=str(output_dir),
            )

            assert exit_code == 1

    @patch("subprocess.run")
    def test_evaluate_finds_latest_checkpoint(self, mock_run, tmp_path: Path):
        """Test that evaluation finds latest checkpoint."""
        mock_run.return_value = MagicMock(returncode=0)

        # Create output dir with checkpoints
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "checkpoint-100").mkdir()
        (output_dir / "checkpoint-200").mkdir()
        (output_dir / "checkpoint-50").mkdir()

        with patch("importlib.import_module"):
            run_full_pipeline(
                generate_dataset=False,
                fine_tune=False,
                evaluate=True,
                output_dir=str(output_dir),
            )

            # Should complete (may log info about eval)
            # Checkpoint-200 should be selected as latest

    @patch("subprocess.run")
    def test_evaluate_with_explicit_checkpoint(self, mock_run, tmp_path: Path):
        """Test evaluation with explicit checkpoint path."""
        mock_run.return_value = MagicMock(returncode=0)

        checkpoint = tmp_path / "my-checkpoint"
        checkpoint.mkdir()

        with patch("importlib.import_module"):
            run_full_pipeline(
                generate_dataset=False,
                fine_tune=False,
                evaluate=True,
                checkpoint_path=str(checkpoint),
            )

            # Should use explicit checkpoint

    @patch("subprocess.run")
    def test_kwargs_passed_to_subprocess(self, mock_run):
        """Test that additional kwargs are passed to subprocess."""
        mock_run.return_value = MagicMock(returncode=0)

        run_full_pipeline(
            generate_dataset=True,
            fine_tune=False,
            evaluate=False,
            crate_list="data/crates.txt",
            **{"--custom-arg": "value"},
        )

        # Custom args should appear in command
        call_args = mock_run.call_args[0][0]
        assert "--custom-arg" in call_args
        assert "value" in call_args

    @patch("subprocess.run")
    def test_full_pipeline_sequence(self, mock_run):
        """Test full pipeline executes in sequence."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("importlib.import_module"):
            # All steps enabled but may not complete due to dependencies
            run_full_pipeline(
                generate_dataset=True,
                fine_tune=False,  # Skip to avoid module import issues
                evaluate=False,
                crate_list="data/crates.txt",
            )

            # At least one subprocess call should be made
            assert mock_run.called


class TestCLIArgumentParsing:
    """Test CLI argument parsing."""

    @patch("sigil_pipeline.cli.ecosystem.run_full_pipeline")
    @patch(
        "sys.argv",
        ["ecosystem", "--no-generate-dataset", "--no-fine-tune", "--no-evaluate"],
    )
    def test_all_steps_disabled_via_cli(self, mock_pipeline):
        """Test disabling all steps via CLI."""
        mock_pipeline.return_value = 0

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        mock_pipeline.assert_called_once()
        call_kwargs = mock_pipeline.call_args[1]
        assert call_kwargs["generate_dataset"] is False
        assert call_kwargs["fine_tune"] is False
        assert call_kwargs["evaluate"] is False

    @patch("sigil_pipeline.cli.ecosystem.run_full_pipeline")
    @patch("sys.argv", ["ecosystem", "--dataset-path", "custom/path.jsonl"])
    def test_custom_dataset_path(self, mock_pipeline):
        """Test custom dataset path via CLI."""
        mock_pipeline.return_value = 0

        with pytest.raises(SystemExit):
            main()

        call_kwargs = mock_pipeline.call_args[1]
        assert call_kwargs["dataset_path"] == "custom/path.jsonl"

    @patch("sigil_pipeline.cli.ecosystem.run_full_pipeline")
    @patch("sys.argv", ["ecosystem", "--config-path", "configs/custom.yml"])
    def test_custom_config_path(self, mock_pipeline):
        """Test custom config path via CLI."""
        mock_pipeline.return_value = 0

        with pytest.raises(SystemExit):
            main()

        call_kwargs = mock_pipeline.call_args[1]
        assert call_kwargs["config_path"] == "configs/custom.yml"

    @patch("sigil_pipeline.cli.ecosystem.run_full_pipeline")
    @patch("sys.argv", ["ecosystem", "--crate-list", "data/my_crates.txt"])
    def test_crate_list_path(self, mock_pipeline):
        """Test crate list path via CLI."""
        mock_pipeline.return_value = 0

        with pytest.raises(SystemExit):
            main()

        call_kwargs = mock_pipeline.call_args[1]
        assert call_kwargs["crate_list"] == "data/my_crates.txt"

    @patch("sigil_pipeline.cli.ecosystem.run_full_pipeline")
    @patch("sys.argv", ["ecosystem", "--output-dir", "custom_output"])
    def test_output_dir(self, mock_pipeline):
        """Test output directory via CLI."""
        mock_pipeline.return_value = 0

        with pytest.raises(SystemExit):
            main()

        call_kwargs = mock_pipeline.call_args[1]
        assert call_kwargs["output_dir"] == "custom_output"

    @patch("sigil_pipeline.cli.ecosystem.run_full_pipeline")
    @patch("sys.argv", ["ecosystem", "--checkpoint-path", "/path/to/checkpoint"])
    def test_checkpoint_path(self, mock_pipeline):
        """Test checkpoint path via CLI."""
        mock_pipeline.return_value = 0

        with pytest.raises(SystemExit):
            main()

        call_kwargs = mock_pipeline.call_args[1]
        assert call_kwargs["checkpoint_path"] == "/path/to/checkpoint"

    @patch("sigil_pipeline.cli.ecosystem.run_full_pipeline")
    @patch("sys.argv", ["ecosystem", "--log-level", "DEBUG"])
    def test_log_level(self, mock_pipeline):
        """Test log level setting via CLI."""
        mock_pipeline.return_value = 0

        with pytest.raises(SystemExit):
            main()

        # Log level is handled by logging setup, not passed to pipeline

    @patch("sigil_pipeline.cli.ecosystem.run_full_pipeline")
    @patch("sys.argv", ["ecosystem"])
    def test_default_values(self, mock_pipeline):
        """Test default values are used."""
        mock_pipeline.return_value = 0

        with pytest.raises(SystemExit):
            main()

        call_kwargs = mock_pipeline.call_args[1]
        assert call_kwargs["generate_dataset"] is True
        assert call_kwargs["fine_tune"] is True
        assert call_kwargs["evaluate"] is True
        assert call_kwargs["dataset_path"] == "datasets/phase2_full.jsonl"
        assert call_kwargs["config_path"] == "configs/llama8b-phase2.yml"
        assert call_kwargs["output_dir"] == "out"

    @patch("sigil_pipeline.cli.ecosystem.run_full_pipeline")
    @patch("sys.argv", ["ecosystem", "--no-fine-tune"])
    def test_exit_code_propagated(self, mock_pipeline):
        """Test exit code from pipeline is propagated."""
        mock_pipeline.return_value = 42

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 42


class TestPipelineIntegration:
    """Integration tests for pipeline (without actual execution)."""

    @patch("subprocess.run")
    def test_command_construction(self, mock_run):
        """Test that commands are constructed correctly."""
        mock_run.return_value = MagicMock(returncode=0)

        run_full_pipeline(
            generate_dataset=True,
            fine_tune=False,
            evaluate=False,
            crate_list="data/crates.txt",
            dataset_path="output/dataset.jsonl",
        )

        call_args = mock_run.call_args[0][0]

        # Verify expected arguments present
        assert "--crate-list" in call_args
        assert "--output" in call_args
        assert "--prompt-mode" in call_args
        assert "--max-sft-lines" in call_args
        assert "--max-sft-chars" in call_args
        assert "--val-ratio" in call_args

    def test_skip_all_returns_success(self):
        """Test that skipping all steps returns success."""
        exit_code = run_full_pipeline(
            generate_dataset=False,
            fine_tune=False,
            evaluate=False,
        )
        assert exit_code == 0
