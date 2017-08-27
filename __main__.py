#!/usr/bin/env python
# coding=utf-8

import codecs
import locale
import os
import signal
import sys
import time

import click

if codecs.lookup(locale.getpreferredencoding()).name == 'ascii':
    os.environ['LANG'] = 'en_US.utf-8'

from dots.interpreter import AsciiDotsInterpreter
from dots.callbacks import IOCallbacksStorage

from dots import terminalsize

try:
    import curses
except ImportError:
    curses = 'failed to import curses; running in compatibility mode'
    print(curses)
    compat_debug_default = True
else:
    compat_debug_default = False

terminal_lines = terminalsize.get_terminal_size()[1]
default_debug_lines = int(terminal_lines * 2 / 3)

interpreter = None

debug_ = True
autostep_debug_ = False


class Default_IO_Callbacks(IOCallbacksStorage):
    def __init__(self, ticks, silent, debug, compat_debug, debug_lines, autostep_debug, head):
        super().__init__()

        self.ticks = ticks
        self.silent = silent
        self.debug = debug
        self.compat_debug = compat_debug
        self.debug_lines = debug_lines
        self.autostep_debug = autostep_debug
        self.head = head

        self.compat_logging_buffer = ''
        self.compat_logging_buffer_lines = terminal_lines - debug_lines - 1

        self.tick_number = 0

        self.output_count = 0

        if self.debug and not self.compat_debug:
            self.logging_loc = 0
            self.logging_x = 1

            self.stdscr = curses.initscr()

            curses.start_color()

            curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
            curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
            curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)

            curses.noecho()

            curses.curs_set(False)

            self.win_program = curses.newwin(self.debug_lines, curses.COLS - 1, 0, 0)

            self.logging_pad = curses.newpad(1000, curses.COLS - 1)

            def signal_handler(signal, frame):
                self.on_finish()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)

            self.first_tick = True
        else:
            self.first_tick = False

    def get_input(self):
        if not self.debug or self.compat_debug:
            if not sys.stdin.isatty():
                return input('')
            else:
                return input('?: ')
        else:
            return self.curses_input(self.stdscr, curses.LINES - 3, 2, '?: ')

    def curses_input(self, stdscr, r, c, prompt_string):
        curses.echo()
        stdscr.addstr(r, c, str(prompt_string), curses.A_REVERSE)
        stdscr.addstr(r + 1, c, " " * (curses.COLS - 1))
        stdscr.refresh()
        input_val = ""

        while len(input_val) <= 0:
            input_val = stdscr.getstr(r + 1, c, 20)

        return input_val

    def on_output(self, value):
        self.output_count += 1

        if self.head != -1 and self.output_count > self.head:
            self.on_finish()
            return

        if self.silent:
            return

        if not self.debug:
            print(value, end='', flush=True)
        elif self.compat_debug:
            self.compat_logging_buffer += value
            self.compat_logging_buffer = '\n'.join(
                self.compat_logging_buffer.split('\n')[:self.compat_logging_buffer_lines])
        else:
            self.logging_pad.addstr(self.logging_loc, self.logging_x, str(value))
            self.logging_pad.refresh(self.logging_loc - min(self.logging_loc, curses.LINES -
                                                            self.debug_lines - 1), 0, self.debug_lines, 0,
                                     curses.LINES - 1, curses.COLS - 1)

            # FIXME: This should count the number of newlines instead
            if str(value).endswith('\n'):
                self.logging_loc += 1
                self.logging_x = 1
            else:
                self.logging_x += len(value)

    def on_finish(self):
        global interpreter

        if self.debug and not self.compat_debug:
            curses.nocbreak()
            self.stdscr.keypad(False)
            curses.echo()

            curses.endwin()

    def on_error(self, error_text):
        self.on_output('error: {}'.format(error_text))

        self.on_finish()

    def on_microtick(self, dot):
        if self.debug and not self.silent:

            d_l = []
            for idx in reversed(range(len(interpreter.get_all_dots()))):
                d = interpreter.dots[idx]
                if not d.state.isDeadState():
                    d_l.append((d.x, d.y))

            special_char = False

            last_blank = False

            display_y = 0

            if self.compat_debug:
                if os.name == 'nt':
                    os.system('cls')  # For Windows
                else:
                    os.system('clear')  # For Linux/OS X
            else:
                self.win_program.refresh()

            for y in range(len(interpreter.world._data_array)):
                if display_y > self.debug_lines - 2:
                    break

                if len(''.join(interpreter.world._data_array[y]).rstrip()) < 1:
                    if last_blank:
                        continue
                    else:
                        last_blank = True
                else:
                    last_blank = False

                for x in range(len(interpreter.world._data_array[y])):
                    char = interpreter.world._data_array[y][x]

                    # RGYB

                    if (x, y) in d_l:
                        if self.compat_debug:
                            print('\033[0;31m' + char + '\033[0m', end='')  # Red
                        else:
                            self.win_program.addstr(display_y, x, char, curses.color_pair(1))
                    elif char.isLibWarp():
                        if self.compat_debug:
                            print('\033[0;32m' + char + '\033[0m', end='')  # Green
                        else:
                            self.win_program.addstr(display_y, x, char, curses.color_pair(2))
                    elif char.isWarp():
                        if self.compat_debug:
                            print('\033[0;33m' + char + '\033[0m', end='')  # Yellow
                        else:
                            self.win_program.addstr(display_y, x, char, curses.color_pair(3))
                    elif char in '#@~' or char.isOper():
                        if self.compat_debug:
                            print('\033[0;34m' + char + '\033[0m', end='')  # Blue
                        else:
                            self.win_program.addstr(display_y, x, char, curses.color_pair(4))
                    elif char == '\n':
                        pass
                    else:
                        if self.compat_debug:
                            print(char, end='')
                        else:
                            self.win_program.addstr(display_y, x, char)

                if self.compat_debug:
                    print()

                display_y += 1

            if self.autostep_debug:
                time.sleep(self.autostep_debug)
            else:
                if self.compat_debug:
                    input("Press enter to step...")
                else:
                    keycode = self.stdscr.getch()

                    if keycode == 3 or keycode == 26:
                        self.on_finish()
                        sys.exit(0)

        if self.compat_debug:
            print('\n' + self.compat_logging_buffer, end='', flush=True)

        if self.ticks is not False:
            if self.tick_number > self.ticks:
                self.on_output('QUITTING next step!\n')

                self.on_finish()
                sys.exit(0)

            self.tick_number += 1


@click.command()
@click.argument('filename')
@click.option('--debug', '-d', is_flag=True, help='Show the execution of the program and the course of the dots.')
@click.option('--autostep_debug', '-a', default=False, help='The time between every tick')
@click.option('--head', '-h', default=-1, help='Terminate the program after N outputs.')
@click.option('--ticks', '-t', default=False, help='Terminate the program after N ticks.')
@click.option('--silent', '-s', is_flag=True, help='No printing, for benchmarking.')
@click.option('--compat_debug', '-w', is_flag=True, help='Force the debug rendering without ncurses.')
@click.option('--debug_lines', '-l', default=default_debug_lines, help='The size of the debug view.')
@click.option('--run_in_parallel', '-p', is_flag=True, help='All dots move at the same time.')
def main(filename, ticks, silent, debug, compat_debug, debug_lines, autostep_debug, head, run_in_parallel):
    global interpreter

    if autostep_debug is not False:
        autostep_debug = float(autostep_debug)

    if ticks is not False:
        ticks = int(ticks)

    head = int(head)

    compat_debug = compat_debug or compat_debug_default

    io_callbacks = Default_IO_Callbacks(ticks, silent, debug, compat_debug, debug_lines, autostep_debug, head)

    file_path = sys.argv[1]

    program_dir = os.path.dirname(os.path.abspath(file_path))

    with open(file_path, 'r') as file:
        program = file.readlines()

    try:
        interpreter = AsciiDotsInterpreter(program, program_dir, io_callbacks, run_in_parallel)
        interpreter.run()
    except Exception as e:
        io_callbacks.on_finish()
        interpreter.terminate()
        raise e


if __name__ == "__main__":
    main()
