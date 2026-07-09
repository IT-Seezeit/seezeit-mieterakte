from unittest import TestCase

from src.path_builder import build_initial_template_names, build_target_paths


class BuildTargetPathsTests(TestCase):
    def test_history_names_are_derived_from_wg_and_room_folders(self) -> None:
        paths = build_target_paths(
            "1000_Leistungsabteilungen/1100_SW/1160_SW_Mieterakten",
            {
                "VO_SUCHNAME": "810-45-01-52-0",
                "WOHNHEIM_SUCHNAME": "810",
                "WOHNHEIM_NAME": "Sonnenbuehl-West-I",
                "PERSON_ID": "202575",
                "VORNAME": "Tabea",
                "NAME": "Bentele",
            },
        )

        base = (
            "1000_Leistungsabteilungen/1100_SW/1160_SW_Mieterakten/"
            "1160_810-Sonnenbuehl-West-I"
        )
        self.assertEqual(paths.wg_path, f"{base}/1160_810-WG-45")
        self.assertEqual(
            paths.wg_history_path,
            f"{base}/1160_810-WG-45/1160_810-45-Historie",
        )
        self.assertEqual(
            paths.room_path,
            f"{base}/1160_810-WG-45/1160_810-45-Zi-01-52-0",
        )
        self.assertEqual(
            paths.room_history_path,
            f"{base}/1160_810-WG-45/1160_810-45-Zi-01-52-0/"
            "1160_810-45-01-52-0-Historie",
        )
        self.assertEqual(
            paths.past_tenants_path,
            f"{base}/1160_810-WG-45/1160_810-45-Zi-01-52-0/"
            "1160_810-45-01-52-0-Vergangene-Mieter",
        )
        self.assertEqual(
            paths.person_path,
            f"{base}/1160_810-WG-45/1160_810-45-Zi-01-52-0/"
            "1160_810-45-01-52-0-202575-Tabea-Bentele",
        )

    def test_single_apartment_uses_wg_00_in_history_name(self) -> None:
        paths = build_target_paths(
            "teamfolder",
            {
                "VO_SUCHNAME": "810- 0 -12",
                "WOHNHEIM_SUCHNAME": "810",
                "WOHNHEIM_NAME": "Wohnheim",
                "PERSON_ID": "1",
                "VORNAME": "Test",
                "NAME": "Person",
            },
        )

        self.assertTrue(paths.wg_path.endswith("/1160_810-WG-00"))
        self.assertTrue(
            paths.wg_history_path.endswith(
                "/1160_810-WG-00/1160_810-00-Historie"
            )
        )
        self.assertTrue(
            paths.room_path.endswith(
                "/1160_810-WG-00/1160_810-00-Zi-12"
            )
        )
        self.assertTrue(
            paths.person_path.endswith(
                "/1160_810-WG-00/1160_810-00-Zi-12/"
                "1160_810-00-12-1-Test-Person"
            )
        )
        self.assertTrue(
            paths.room_history_path.endswith(
                "/1160_810-00-Zi-12/1160_810-00-12-Historie"
            )
        )
        self.assertTrue(
            paths.past_tenants_path.endswith(
                "/1160_810-00-Zi-12/"
                "1160_810-00-12-Vergangene-Mieter"
            )
        )

    def test_initial_template_names_use_normalized_location_and_person_id(self) -> None:
        names = build_initial_template_names(
            {
                "VO_SUCHNAME": "810-45-01-52-0",
                "WOHNHEIM_SUCHNAME": "810",
                "PERSON_ID": "202575",
            }
        )

        self.assertEqual(
            names,
            {
                "Auszugsprotokoll.pdf":
                    "1160_810-45-01-52-0-Auszugsprotokoll-202575.pdf",
                "Einzugsprotokoll.pdf":
                    "1160_810-45-01-52-0-Einzugsprotokoll-202575.pdf",
            },
        )
