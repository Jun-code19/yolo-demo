"""Analyze person search query case with Parsing/PAR attributes."""
import cv2

from src.person_search.embedder import _blend_similarity, passes_match_gate
from src.person_search.par_attrs import compare_person_attributes, extract_person_attributes
from src.person_search.utils import strip_segmentation_border

BASE = r"C:\Users\24484\.cursor\projects\d-PythonData-yolo-client-demo-yolo-demo\assets"
PATHS = [
    (
        "query_yellow_jacket_girl",
        BASE
        + r"\c__Users_24484_AppData_Roaming_Cursor_User_workspaceStorage_37c95758fabc3fabe5676191bfc37746_images_590e3f3e-15e7-4b4b-800d-04b604162ea4_0-b8aaaca3-5308-470a-8441-3f6c889d6213.jpg",
    ),
    (
        "white_tee_girl",
        BASE
        + r"\c__Users_24484_AppData_Roaming_Cursor_User_workspaceStorage_37c95758fabc3fabe5676191bfc37746_images_fd801f94-b7e5-4cd1-bc09-7c1bfe9716ac_0-a27210df-cd58-4df9-bab1-64628bc4b1f2.jpg",
    ),
    (
        "wrong_man",
        BASE
        + r"\c__Users_24484_AppData_Roaming_Cursor_User_workspaceStorage_37c95758fabc3fabe5676191bfc37746_images_0506aa01-8b99-4764-9414-6b9fd6559c50_0-dc1c9620-5444-4f5c-a51d-a2ab099c7e7b.jpg",
    ),
]


def main() -> None:
    attrs_map = {}
    for name, path in PATHS:
        bgr = cv2.imread(path)
        clean = strip_segmentation_border(bgr)
        attrs = extract_person_attributes(clean)
        attrs_map[name] = attrs
        print(f"=== {name} ===")
        print(
            f"  gender={attrs.get('gender')}({attrs.get('gender_conf')}) "
            f"upper={attrs.get('upper_color')}({attrs.get('upper_color_conf')}) "
            f"lower={attrs.get('lower_color')}({attrs.get('lower_color_conf')}) "
            f"sleeve={attrs.get('upper_sleeve')} source={attrs.get('source')}"
        )

    print()
    q = attrs_map["query_yellow_jacket_girl"]
    for name in ["white_tee_girl", "wrong_man"]:
        cmp_result = compare_person_attributes(q, attrs_map[name])
        print(f"--- query vs {name} ---")
        print(f"  attr_cmp={cmp_result}")
        for deep in [0.55, 0.62, 0.68, 0.72]:
            blend = _blend_similarity(
                deep,
                0.5,
                0.5,
                0.5,
                0.5,
                float(cmp_result.get("similarity") or -1),
                attrs_veto=bool(cmp_result.get("veto")),
            )
            gate = passes_match_gate(
                deep,
                0.5,
                0.5,
                0.5,
                0.5,
                bool(cmp_result.get("veto")),
                float(cmp_result.get("similarity") or -1),
            )
            print(f"  deep={deep:.2f} blend={blend:.3f} gate={gate}")


if __name__ == "__main__":
    main()
