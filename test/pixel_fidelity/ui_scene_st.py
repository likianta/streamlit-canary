"""
A general UI components set for pixel fidelity test.
This script is hosting Streamlit app.
"""

from time import sleep

import pandas as pd
import streamlit as st


def main():
    with st.container(horizontal=True, vertical_alignment='bottom'):
        st.selectbox(
            'Select device', ('ASA EMEI r6p0', 'Fake device', 'Remote device')
        )
        st.number_input(
            'Channel',
            min_value=0,
            max_value=3,
            value=0,
            step=1,
            help='Available channels can be read from `0xF102[3:0]`.',
            #   single-line help.
        )
        st.button('Start eye monitor', type='primary', width='stretch')
        with st.popover(':material/adjust:', help='Line calibration'):
            with st.container(width=540):
                _line_calibration()

    st.markdown(
        'Material icons: '
        ':material/adjust: '
        ':material/settings_backup_restore: '
        ':orange[:material/brightness_auto:]'
    )

    _radio()
    _slider()
    _table()
    _progress()
    _toggle()
    _exception()


def _radio():
    st.radio('Radio', ('Option A', 'Option B', 'Option C'))
    cols = st.columns((2, 3))
    with cols[0]:
        st.radio(
            'Radio (horizontal, narrow)',
            (7, 8, 9, 10, 11, 12),
            index=3,
            horizontal=True,
        )
    with cols[1]:
        st.caption('A horizontal radio wraps inside a narrow column.')


def _slider():
    st.select_slider(
        'Select slider',
        tuple(range(15, 0, -1)),
        value=15,
        format_func=lambda x: 'Lv.{}'.format(x),
    )


def _exception():
    if st.button(':red[Raise an error]'):
        raise Exception('Test error')


def _progress():
    # a determinate bar: it starts at 37% so the pixel tests have a fixed
    # value to compare, and the button runs it through 1..100.
    bar = st.progress(37, '37%')
    if st.button('Run progress bar'):
        for i in range(100):
            sleep(0.03)
            bar.progress(i + 1, '{}%'.format(i + 1))


def _toggle():
    # switches in a horizontal container pack onto one line; the asa_gui
    # batch-script page relies on that (three toggles plus a bar in one row).
    with st.container(horizontal=True, vertical_alignment='center'):
        st.toggle('Show index', True)
        st.toggle('Show separator line')
        st.toggle('Show full list')
        st.progress(37, '37%')


def _line_calibration() -> None:
    calib_tabs = st.tabs(('One-line Calibration', 'Two-line Calibration'))
    with calib_tabs[0]:
        with st.container(horizontal=True, vertical_alignment='bottom'):
            cols = st.columns((5, 2), vertical_alignment='bottom')
            with cols[0]:
                st.number_input(
                    'What is your physical line length',
                    value=5,
                    min_value=1,
                    max_value=100,
                    step=1,
                    help='Unit: meter',
                )
            with cols[1]:
                st.number_input(
                    'Bias',
                    min_value=0.0,
                    max_value=20.0,
                    value=2.0,
                    step=1.0,
                    format='%0.1f',
                    help=(  # multi-line help
                        """
                        The Bias parameter is used to measure the pulse offset 
                        caused by the routing design on the PCB board. 

                        Roughly speaking, you can take count of each 3cm trace 
                        length as 1 point, and considering the round trip, the 
                        trace and the number of points need to be multiplied by 
                        2 respectively.

                        For example: If the routing distance is approximately 
                        2.5 cm, then the *bias* value should be 
                        `(2.5 * 2) / 3 = 1.67` (float-type is supported).
                        """
                    ),
                )
            st.button('Start calibration')
    with calib_tabs[1]:
        with st.container(horizontal=True, vertical_alignment='bottom'):
            st.text_input(
                'First line length',
                '1m@ch0',
                help=(  # help text, markdown with table
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
            st.button('Calibrate', key='_:two_line_calib:calib_btn_1')
            st.text_input(
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
            st.button('Calibrate', key='_:two_line_calib:calib_btn_2')


def _table():
    st.table(
        {
            'Link status': ':green[ON]',
            'PRBS error counter': ':red[123]',
            'Server connected': 'Fake device',
        },
        width='content',
    )
    st.table(
        {
            'File name': 'droo1.mat',
            'File size': '28.19KB',
            'MATLAB version': '7.3',
        },
        width='stretch',  # default
    )
    st.table(
        pd.DataFrame(
            {
                'Value': ['ON', '123', 'Fake device'],
                'Detail': ['ok', 'warn', 'info'],
            },
            index=['Link status', 'PRBS error counter', 'Server connected'],
        ),
        width='content',
    )


if __name__ == '__main__':
    # python -m streamlit run --runner.magicEnabled false \
    #   --server.headless true --server.port 2202 \
    #   test/pixel_fidelity/ui_scene_st.py
    main()
