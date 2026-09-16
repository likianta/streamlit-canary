"""
A general UI components set for pixel fidelity test.
This script is hosting Streamlit Canary app.
"""

from time import sleep

import streamlit_canary as sc
from streamlit_canary import components_v3 as v3


def main():
    with v3.Row('bottom'):
        v3.Selectbox(
            'Select device', ('ASA EMEI r6p0', 'Fake device', 'Remote device')
        )
        v3.NumberInput(
            *('Channel', 0, 0, 3, 1),
            #   positional arguments: label, value, min_value, max_value, step
            help='Available channels can be read from `0xF102[3:0]`.',
        )
        v3.Button('Start eye monitor', type='primary', width='stretch')
        with v3.Popover(':material/adjust:', help='Line calibration'):
            with v3.Container(width=540):
                _line_calibration()

    v3.Markdown(
        'Material icons: '
        ':material/adjust: '
        ':material/settings_backup_restore: '
        ':orange[:material/brightness_auto:]'
    )

    _table()

    _progress()

    _exception()


def _exception():
    with v3.Button(':red[Raise an error]') as btn:

        @btn.on_click
        def _():
            raise Exception('Test error')


def _progress():
    # a determinate bar: it starts at 37% so the pixel tests have a fixed
    # value to compare, and the button runs it through 1..100.  The handler
    # blocks in a worker thread (see `runtime/server.py`), so the patches it
    # emits reach the browser while the loop is still running.
    bar = v3.Progress(37, text='37%', visible=True)
    with v3.Button('Run progress bar') as btn:

        @btn.on_click
        def _run() -> None:
            for i in range(100):
                sleep(0.03)
                bar['value'] = i + 1
                bar['text'] = '{}%'.format(i + 1)


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
            with v3.Row('bottom'):
                v3.TextInput(
                    'First line length',
                    '1m@ch0',
                    help=(
                        """
                        Supported format:

                        | Example  | Result                   | Note        |
                        | -------- | ------------------------ | ----------- |
                        | `1`      | channel=0, line_lengh=1m |             |
                        | `1m`     | channel=0, line_lengh=1m | recommended |
                        | `1m@ch0` | channel=0, line_lengh=1m | recommended |
                        | `1m@0`   | channel=0, line_lengh=1m |             |
                        | `1@0`    | channel=0, line_lengh=1m |             |
                        """
                    ),
                )
                v3.Button('Calibrate')
                v3.TextInput(
                    'Second line length',
                    '2m@ch1',
                    help=(
                        """
                        Supported format:

                        | Example  | Result                   | Note        |
                        | -------- | ------------------------ | ----------- |
                        | `1`      | channel=0, line_lengh=1m |             |
                        | `1m`     | channel=0, line_lengh=1m | recommended |
                        | `1m@ch0` | channel=0, line_lengh=1m | recommended |
                        | `1m@0`   | channel=0, line_lengh=1m |             |
                        | `1@0`    | channel=0, line_lengh=1m |             |
                        """
                    ),
                )
                v3.Button('Calibrate')


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
