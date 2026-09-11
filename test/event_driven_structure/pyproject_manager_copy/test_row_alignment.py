"""
Verify Row(vertical_alignment='bottom') via element geometry.

Queries the runtime's `/geometry/{id}` HTTP endpoint (populated by the
frontend's periodic getBoundingClientRect reports) and asserts that the
Selectbox and the icon Button in the top row share the same bottom edge.

Run:
    python test/event_driven_structure/pyproject_manager_copy/test_row_alignment.py
"""

import requests

BASE = 'http://127.0.0.1:3001'


def get_element_absolute_geometry(key: str) -> dict:
    """Return cached geometry {x, y, width, height} for a component key."""
    resp = requests.get(f'{BASE}/geometry/{key}')
    resp.raise_for_status()
    return resp.json()


def verify_bottom_align(scope_sel_key: str, refresh_btn_key: str) -> None:
    g1 = get_element_absolute_geometry(key=scope_sel_key)
    g2 = get_element_absolute_geometry(key=refresh_btn_key)
    print('scope_sel  geometry:', g1)
    print('refresh_btn geometry:', g2)
    bottom1 = g1['y'] + g1['height']
    bottom2 = g2['y'] + g2['height']
    print('scope_sel  bottom =', bottom1)
    print('refresh_btn bottom =', bottom2)
    print('diff =', abs(bottom1 - bottom2))
    # Allow sub-pixel rounding tolerance (≤ 1px).
    assert abs(bottom1 - bottom2) <= 1, (
        f'bottom mismatch: scope_sel bottom={bottom1} '
        f'refresh_btn bottom={bottom2} diff={abs(bottom1 - bottom2)}'
    )
    print('PASS: bottoms aligned')


if __name__ == '__main__':
    verify_bottom_align('scope_sel', 'refresh_btn')
