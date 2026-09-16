"""
A general UI components set for pixel fidelity test.
This script is hosting Streamlit Canary app.
"""

import streamlit_canary as sc
from streamlit_canary import components_v3 as v3


def main():
    with v3.Row('bottom'):
        v3.Selectbox(
            'Select device', ('ASA EMEI r6p0', 'Fake device', 'Remote device')
        )
        v3.NumberInput('Channel', 0, 0, 3, 1)
        #   positional arguments: label, value, min_value, max_value, step
        v3.Button('Start eye monitor', type='primary', width='stretch')
        with v3.Popover(':material/adjust:', help='Line calibration'):
            with v3.Container(width=540):
                _line_calibration()
    _table()


def _line_calibration() -> None:
    with v3.Tabs(('One-line Calibration', 'Two-line Calibration')) as tabs:
        with next(tabs):
            with v3.Row('bottom'):
                with v3.Grid(
                    rows=1, cols=(5, 2), vertical_alignment='bottom'
                ) as grid:
                    with next(grid):
                        v3.NumberInput(
                            'What is your physical line length',
                            5,
                            1,
                            100,
                            1,
                            help='Unit: meter',
                        )
                    with next(grid):
                        v3.NumberInput(
                            'Bias',
                            2.0,
                            0,
                            20,
                            1,
                            format=lambda x: '{:.1f}'.format(x),
                            help=(
                                """
                                The Bias parameter is used to measure the pulse 
                                offset caused by the routing design on the PCB 
                                board. 

                                Roughly speaking, you can take count of each 3cm 
                                trace length as 1 point, and considering the 
                                round trip, the trace and the number of points 
                                need to be multiplied by 2 respectively.

                                For example: If the routing distance is 
                                approximately 2.5 cm, then the *bias* value 
                                should be `(2.5 * 2) / 3 = 1.67` (float-type is 
                                supported).
                                """
                            ),
                        )
                v3.Button('Start calibration')
        with next(tabs):
            ...


def _table():
    v3.Table(
        (
            ('Link status', ':green[ON]'),
            ('PRBS error counter', ':red[123]'),
            ('Server connected', 'Fake device'),
        ),
        width='content',
    )
    v3.Table(
        (
            ('File name', 'droo1.mat'),
            ('File size', '28.19KB'),
            ('MATLAB version', '7.3'),
        ),
        width='stretch',  # default
    )


if __name__ == '__main__':
    # python test/pixel_fidelity/ui_scene_sc.py
    sc.run(main, port=2203)
