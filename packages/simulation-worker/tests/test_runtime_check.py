from pathlib import Path

import pytest
from earthmind_worker.runtime_check import parse_tripinfo


def test_trip_output_requires_two_actual_completed_vehicle_records(tmp_path: Path) -> None:
    output = tmp_path / "tripinfo.xml"
    output.write_text("<tripinfos><tripinfo id='only_one'/></tripinfos>")
    with pytest.raises(RuntimeError, match="Expected 2 completed trips"):
        parse_tripinfo(output)


def test_trip_output_preserves_measured_arrival_values(tmp_path: Path) -> None:
    output = tmp_path / "tripinfo.xml"
    output.write_text(
        "<tripinfos>"
        "<tripinfo id='probe_0' depart='0' arrival='22' duration='22' routeLength='195'/>"
        "<tripinfo id='probe_1' depart='2' arrival='25' duration='23' routeLength='195'/>"
        "</tripinfos>"
    )
    trips = parse_tripinfo(output)
    assert len(trips) == 2
    assert trips[1]["arrival"] == "25"
