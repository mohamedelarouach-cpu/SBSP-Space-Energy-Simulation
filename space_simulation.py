#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
JAXA/MHI PRECISION CURSOR DASHBOARD v34.0 (CONTINUOUS SCROLLING – LIVE STREAM)
================================================================================
- Infinite scrolling X‑axis: new data enters from right, old exits left.
- Sharp, sudden vertical drops/peaks (random walk with large steps).
- Side panel updates in real‑time with 3‑decimal precision.
- Neon blue, ultra‑thin (0.8pt), balanced speed (interval=30ms).
- No static lines, no wrap‑around – pure continuous streaming.
================================================================================
"""

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.animation import FuncAnimation
import math
import csv
import warnings
import os
from collections import deque

warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


# ============================================================
# 1. PHYSICS ENGINE – SHARP RANDOM WALK
# ============================================================
class SpacePowerStation:
    def __init__(self, area=1000.0, demand=500.0):
        self.area = area
        self.demand = demand
        self.total_gen_kwh = 0.0
        self.total_cons_kwh = 0.0
        self.total_sim_seconds = 0.0

        self.rpm = 0.0
        self.stored_kwh = 0.0
        self.plasma_power = 0.0
        self.plasma_consumed_kwh = 0.0
        self.honeypot_attacks = 0
        self.attack_flag = False
        self.attack_time = 0
        self.passive_eff = 0.8
        self.honeypot_active = False

        self.solar_value = 500.0
        self.rpm_value = 20000.0
        self.def_value = 40.0
        self.plasma_value = 5.0

        self.prev_power = 0.0
        self.prev_rpm = 0.0
        self.prev_def = 0.0
        self.prev_plasma = 0.0
        self.prev_solar = 0.0
        self.prev_stored = 0.0

    def generate_weather(self, hour):
        temp = 30 + 15 * math.sin(math.pi * hour / 12.0)
        wind = 3 + 12 * abs(math.sin(math.pi * hour / 8.0))
        return {"temp": temp, "wind": wind}

    def solar_power(self):
        step = np.random.normal(0, 25)
        self.solar_value += step
        self.solar_value = max(200.0, min(self.solar_value, 900.0))
        return self.solar_value

    def generate_dust(self, hour, wind):
        base = max(0, wind * 0.4)
        defense = 1.0 - (self.passive_eff * 0.8)
        final = base * defense
        num = int(min(final, 12))
        particles = []
        rng = np.random.RandomState(int(hour * 100) % 1000)
        for _ in range(num):
            particles.append({
                'y': rng.uniform(0.2, 2.8),
                'charge': rng.uniform(0.8, 2.2),
                'vel': rng.uniform(0.8, 1.8)
            })
        return particles, defense

    def compute_plasma(self, particles):
        if not particles:
            return 0.0, 0.0
        N = len(particles)
        avg_q = sum(p['charge'] for p in particles) / N
        avg_v = sum(p['vel'] for p in particles) / N
        required = ((N / 10.0) ** 2) * avg_q * avg_v / 0.5
        power = min(required, 50.0)
        if power > self.plasma_power:
            self.plasma_power += (power - self.plasma_power) * 0.15
        else:
            self.plasma_power += (power - self.plasma_power) * 0.3
        self.plasma_power = max(0.0, min(self.plasma_power, 50.0))

        deflected = 0
        if self.plasma_power > 1.0:
            for p in particles:
                dist = max(p['y'], 0.1)
                force = (p['charge'] * self.plasma_power) / (dist ** 2)
                if force > p['vel'] * 0.85:
                    deflected += 1
        rate = (deflected / len(particles)) * 100.0 if particles else 0.0
        return rate, self.plasma_power

    def update_flywheel(self, surplus, dt_sec):
        max_rpm = 30000.0
        inertia = 100.0
        if surplus > 0:
            energy_kj = surplus * dt_sec
            omega_cur = self.rpm * 2.0 * math.pi / 60.0
            omega_sq = (2.0 * energy_kj / inertia) + (omega_cur ** 2)
            if omega_sq > 0:
                new_rpm = math.sqrt(omega_sq) * 60.0 / (2.0 * math.pi)
                self.rpm = min(new_rpm, max_rpm)
                self.stored_kwh = (0.5 * inertia * (self.rpm * 2.0 * math.pi / 60.0) ** 2) / 3600.0

    def step(self, dt_sec):
        self.total_sim_seconds += dt_sec
        hour = self.total_sim_seconds / 3600.0  # continuous, not modulo

        solar_noisy = self.solar_power()

        loss = 0.001
        effective = solar_noisy * (1 - loss)
        received_noisy = effective * 0.98
        received_noisy = max(200.0, min(received_noisy, 900.0))

        weather = self.generate_weather(hour % 24.0)  # weather based on time of day
        particles, grid_eff = self.generate_dust(hour % 24.0, weather['wind'])
        def_rate_det, plasma_pwr_det = self.compute_plasma(particles)
        self.plasma_consumed_kwh += (plasma_pwr_det * dt_sec) / 3600.0

        # Cyber attack window based on hour-of-day (mod 24)
        hour_of_day = hour % 24.0
        if 14.0 <= hour_of_day <= 16.0:
            if not self.attack_flag:
                self.attack_flag = True
                self.attack_time = hour
                self.honeypot_attacks += 1
                self.honeypot_active = True
        else:
            if self.attack_flag and (hour - self.attack_time) > 2.0:
                self.attack_flag = False
                self.honeypot_active = False

        if received_noisy < self.demand:
            deficit = self.demand - received_noisy
            max_release_kwh = min(deficit * dt_sec / 3600.0, self.stored_kwh * 0.9)
            if max_release_kwh > 0:
                received_noisy += max_release_kwh * 3600.0 / dt_sec
                self.stored_kwh -= max_release_kwh
                if self.stored_kwh < 0.001:
                    self.stored_kwh = 0.0
                    self.rpm = 0.0
                else:
                    inertia = 100.0
                    energy_j = self.stored_kwh * 3600.0 * 1000.0
                    omega = math.sqrt((2.0 * energy_j) / inertia)
                    self.rpm = omega * 60.0 / (2.0 * math.pi)
                    self.rpm = min(self.rpm, 30000.0)
            received_noisy = max(200.0, min(received_noisy, 900.0))

        surplus = received_noisy - self.demand
        if surplus > 0:
            self.update_flywheel(surplus, dt_sec)

        self.total_gen_kwh += (solar_noisy * dt_sec) / 3600.0
        self.total_cons_kwh += (received_noisy * dt_sec) / 3600.0

        # Sharp random walk for RPM
        step_rpm = np.random.normal(0, 800)
        self.rpm_value += step_rpm
        self.rpm_value = max(5000.0, min(self.rpm_value, 30000.0))
        rpm_noisy = self.rpm_value

        # Sharp random walk for Deflection
        step_def = np.random.normal(0, 8)
        self.def_value += step_def
        self.def_value = max(5.0, min(self.def_value, 85.0))
        def_noisy = self.def_value

        plasma_noisy = plasma_pwr_det + np.random.normal(0, 0.5)
        plasma_noisy = max(0.0, min(plasma_noisy, 50.0))

        capacity_noisy = (rpm_noisy / 30000.0) * 100.0
        capacity_noisy = min(capacity_noisy, 100.0)

        return {
            'hour': hour,
            'temp': weather['temp'],
            'wind': weather['wind'],
            'solar': solar_noisy,
            'received': received_noisy,
            'demand': self.demand,
            'surplus': surplus,
            'def_rate': def_noisy,
            'plasma_pwr': plasma_noisy,
            'rpm': rpm_noisy,
            'stored': self.stored_kwh,
            'capacity': capacity_noisy,
            'grid_eff': grid_eff * 100,
            'attacks': self.honeypot_attacks,
            'attack_flag': self.attack_flag,
            'total_gen': self.total_gen_kwh,
            'total_cons': self.total_cons_kwh
        }


# ============================================================
# 2. DASHBOARD – CONTINUOUS SCROLLING (DEQUE)
# ============================================================
class PrecisionCursorDashboard:
    def __init__(self, station, speed_factor=150.0, window_hours=1.0):
        self.station = station
        self.speed_factor = speed_factor
        self.window_hours = window_hours
        self.running = True

        # Maximum points to keep (1 point per second)
        self.max_points = int(window_hours * 3600)

        # Deques for rolling data
        self.time_win = deque(maxlen=self.max_points)
        self.solar_win = deque(maxlen=self.max_points)
        self.received_win = deque(maxlen=self.max_points)
        self.rpm_win = deque(maxlen=self.max_points)
        self.deflection_win = deque(maxlen=self.max_points)
        self.plasma_win = deque(maxlen=self.max_points)
        self.attack_win = deque(maxlen=self.max_points)

        # Pre‑fill with a few points
        print(" [JAXA] Initialising continuous scrolling buffer ({} h window)...".format(window_hours))
        for _ in range(100):
            data = station.step(1.0)
            self._add_point(data)
        print(" [JAXA] Ready. Starting continuous scrolling animation.")

        # ---- Theme (neon blue) ----
        self.bg = '#FFFFFF'
        self.fg = '#000000'
        self.grid = '#E0E0E0'
        self.axis = '#333333'
        self.line_color = '#00AAFF'
        self.line_width = 0.8
        self.safe_border = '#00994D'
        self.alert_border = '#CC0000'

        # ---- Figure ----
        self.fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=self.bg)
        self.fig.suptitle("JAXA SBSP GROUND CONTROL  |  v34.0 (CONTINUOUS STREAMING)",
                          fontsize=14, fontweight='bold', color=self.fg)

        gs = GridSpec(3, 2, figure=self.fig, width_ratios=[2.6, 1],
                      hspace=0.4, wspace=0.3, top=0.92, bottom=0.08)

        self.ax1 = self.fig.add_subplot(gs[0, 0])
        self.ax2 = self.fig.add_subplot(gs[1, 0])
        self.ax3 = self.fig.add_subplot(gs[2, 0])
        self.ax_info = self.fig.add_subplot(gs[:, 1])
        self.ax_info.axis('off')

        # ---- Axes (dynamic xlim, fixed ylim) ----
        for ax in (self.ax1, self.ax2, self.ax3):
            ax.set_facecolor(self.bg)
            ax.set_xlabel('Time (hours)', fontsize=10, color=self.axis)
            ax.tick_params(colors=self.axis, labelsize=9)
            ax.grid(True, alpha=0.4, color=self.grid, linestyle='--', linewidth=1)

        self.ax1.set_ylim(0, 1000)
        self.ax1.set_ylabel('Power (kW)', fontsize=10, color=self.axis)
        self.ax1.set_yticks([0, 200, 400, 600, 800, 1000])
        self.ax1.set_yticklabels(['0', '200', '400', '600', '800', '1000'])

        self.ax2.set_ylim(0, 35000)
        self.ax2.set_ylabel('RPM', fontsize=10, color=self.axis)
        self.ax2.set_yticks([0, 5000, 10000, 15000, 20000, 25000, 30000])
        self.ax2.set_yticklabels(['0', '5k', '10k', '15k', '20k', '25k', '30k'])

        self.ax3.set_ylim(0, 105)
        self.ax3.set_ylabel('Deflection Rate (%)', fontsize=10, color=self.axis)
        self.ax3.set_yticks([0, 20, 40, 60, 80, 100])

        self.ax3_twin = self.ax3.twinx()
        self.ax3_twin.set_ylim(0, 60)
        self.ax3_twin.set_ylabel('Plasma Power (kW)', fontsize=10, color=self.axis)
        self.ax3_twin.set_yticks([0, 15, 30, 45, 60])

        # ---- Lines (neon blue) ----
        self.line_power, = self.ax1.plot([], [], color=self.line_color, linewidth=self.line_width, label='Received')
        self.line_solar, = self.ax1.plot([], [], color=self.line_color, linewidth=self.line_width, label='Solar')
        self.line_rpm, = self.ax2.plot([], [], color=self.line_color, linewidth=self.line_width, label='RPM')
        self.line_def, = self.ax3.plot([], [], color=self.line_color, linewidth=self.line_width, label='Deflection')
        self.line_plasma, = self.ax3_twin.plot([], [], color=self.line_color, linewidth=self.line_width, label='Plasma')

        # ---- Attack scatter ----
        self.attack_scatter = self.ax1.scatter([], [], color='#CC0000', s=120, marker='^', alpha=1.0, label='Cyber Attack')

        # ---- Info panel ----
        self.text_info = self.ax_info.text(
            0.05, 0.98, "",
            transform=self.ax_info.transAxes,
            fontsize=10,
            verticalalignment='top',
            fontfamily='monospace',
            color=self.fg,
            linespacing=1.5,
            bbox=dict(facecolor='#F5F5F5', edgecolor=self.safe_border,
                      linewidth=3, boxstyle='round,pad=1.2')
        )

        plt.tight_layout(pad=1.5, rect=[0, 0, 1, 0.94])

        # CSV logger
        self.csv_file = open('jaxa_v34_scroll.csv', 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            'Hour', 'Solar_kW', 'Received_kW', 'Flywheel_RPM',
            'Deflection_Pct', 'Plasma_kW', 'Stored_kWh', 'Surplus_kW',
            'Grid_Eff_Pct', 'Cyber_Attacks'
        ])

        self.attack_detected = False
        self.attack_timer = 0
        self.prev_power = 0.0
        self.prev_rpm = 0.0
        self.prev_def = 0.0
        self.prev_plasma = 0.0
        self.prev_solar = 0.0

        self.step_size = 50  # points per frame

    def _add_point(self, data):
        """Append one data point to deques."""
        self.time_win.append(data['hour'])
        self.solar_win.append(data['solar'])
        self.received_win.append(data['received'])
        self.rpm_win.append(data['rpm'])
        self.deflection_win.append(data['def_rate'])
        self.plasma_win.append(data['plasma_pwr'])
        self.attack_win.append(1 if data['attack_flag'] else 0)

    def get_arrow(self, current, previous):
        if previous is None or previous == 0:
            return ' ', self.fg
        diff = current - previous
        if diff > 0.01:
            return '▲', '#00CC00'
        elif diff < -0.01:
            return '▼', '#FF0000'
        else:
            return ' ', self.fg

    def update_frame(self, frame):
        # ---- Generate new points ----
        for _ in range(self.step_size):
            data = self.station.step(1.0)
            self._add_point(data)
            self.csv_writer.writerow([
                f"{data['hour']:.3f}", f"{data['solar']:.3f}", f"{data['received']:.3f}",
                f"{data['rpm']:.3f}", f"{data['def_rate']:.3f}", f"{data['plasma_pwr']:.3f}",
                f"{data['stored']:.3f}", f"{data['surplus']:.3f}",
                f"{data['grid_eff']:.3f}", f"{data['attacks']:.0f}"
            ])
            self.csv_file.flush()

        # ---- Get current deques as lists ----
        t = list(self.time_win)
        solar = list(self.solar_win)
        received = list(self.received_win)
        rpm = list(self.rpm_win)
        deflection = list(self.deflection_win)
        plasma = list(self.plasma_win)
        attack = list(self.attack_win)

        # ---- Update x‑axis limits (scrolling) ----
        if len(t) > 0:
            current_time = t[-1]
            left = max(0.0, current_time - self.window_hours)
            # If the stream is still in the first window, keep left = 0
            if current_time < self.window_hours:
                left = 0.0
            self.ax1.set_xlim(left, current_time)
            self.ax2.set_xlim(left, current_time)
            self.ax3.set_xlim(left, current_time)

        # ---- Update lines ----
        self.line_power.set_data(t, received)
        self.line_solar.set_data(t, solar)
        self.line_rpm.set_data(t, rpm)
        self.line_def.set_data(t, deflection)
        self.line_plasma.set_data(t, plasma)

        # ---- Attack scatter ----
        if len(t) > 0:
            attack_times = [t[i] for i in range(len(t)) if attack[i] == 1]
            if attack_times:
                attack_y = [600] * len(attack_times)
                self.attack_scatter.set_offsets(np.column_stack((attack_times, attack_y)))
                self.attack_scatter.set_sizes([120] * len(attack_times))
            else:
                self.attack_scatter.set_offsets(np.empty((0, 2)))
        else:
            self.attack_scatter.set_offsets(np.empty((0, 2)))

        # ---- Status panel (high precision, 3 decimals) ----
        if len(t) > 0:
            # Latest data point (last element)
            latest = {
                'hour': t[-1],
                'solar': solar[-1],
                'received': received[-1],
                'rpm': rpm[-1],
                'def_rate': deflection[-1],
                'plasma_pwr': plasma[-1],
                'attack': attack[-1]
            }
            total_gen = self.station.total_gen_kwh
            total_cons = self.station.total_cons_kwh
            net = total_gen - total_cons
            efficiency = ((total_gen * 0.6 - total_cons) / (total_gen * 0.6)) * 100 if total_gen > 0 else 0

            arrow_power, _ = self.get_arrow(latest['received'], self.prev_power)
            arrow_rpm, _ = self.get_arrow(latest['rpm'], self.prev_rpm)
            arrow_def, _ = self.get_arrow(latest['def_rate'], self.prev_def)
            arrow_plasma, _ = self.get_arrow(latest['plasma_pwr'], self.prev_plasma)
            arrow_solar, _ = self.get_arrow(latest['solar'], self.prev_solar)

            self.prev_power = latest['received']
            self.prev_rpm = latest['rpm']
            self.prev_def = latest['def_rate']
            self.prev_plasma = latest['plasma_pwr']
            self.prev_solar = latest['solar']

            is_attack = bool(latest['attack'])
            if is_attack:
                self.attack_detected = True
                self.attack_timer = 30
                border_color = self.alert_border
                face_color = '#FFE6E6'
                text_color = '#CC0000'
            elif self.attack_timer > 0:
                self.attack_timer -= 1
                if self.attack_timer == 0:
                    self.attack_detected = False
                border_color = self.alert_border if self.attack_timer > 0 else self.safe_border
                face_color = '#FFE6E6' if self.attack_timer > 0 else '#F5F5F5'
                text_color = '#CC0000' if self.attack_timer > 0 else self.fg
            else:
                border_color = self.safe_border
                face_color = '#F5F5F5'
                text_color = self.fg

            self.text_info.set_bbox(dict(
                facecolor=face_color,
                edgecolor=border_color,
                linewidth=3 if self.attack_detected else 2,
                boxstyle='round,pad=1.2'
            ))
            self.text_info.set_color(text_color)

            # Display with 3 decimals and comma thousands
            info_text = (
                "=== STATUS PANEL ===\n"
                f"Time    : {latest['hour']:7.3f} h\n"
                "Temp    : (not stored)\n"
                "Wind    : (not stored)\n"
                "--------------------\n"
                f"Solar   : {latest['solar']:8.3f} kW {arrow_solar}\n"
                f"Received: {latest['received']:8.3f} kW {arrow_power}\n"
                f"Demand  : {self.station.demand:7.0f} kW\n"
                f"Surplus : {latest['received'] - self.station.demand:8.3f} kW\n"
                "--------------------\n"
                f"Plasma  : {'ACTIVE' if latest['plasma_pwr']>1 else 'STANDBY'}\n"
                f" Power  : {latest['plasma_pwr']:8.3f} kW {arrow_plasma}\n"
                f" Defl   : {latest['def_rate']:8.3f} % {arrow_def}\n"
                "--------------------\n"
                f"Flywheel RPM : {latest['rpm']:9.3f} {arrow_rpm}\n"
                f" Stored kWh  : {self.station.stored_kwh:9.3f}\n"
                f" Capacity %  : {(latest['rpm']/30000.0)*100:8.3f}  [CLAMPED ≤ 100%]\n"
                "--------------------\n"
                f"Passive Grid : (not stored)\n"
                f"Cyber Attacks: {self.station.honeypot_attacks:5d}\n"
                f"Honeypot     : {'ACTIVE' if is_attack else 'IDLE'}\n"
                f"Status       : {'>>> ALERT <<<' if self.attack_detected else 'SECURE'}\n"
                "--------------------\n"
                f"Gen kWh  : {total_gen:10.3f}\n"
                f"Cons kWh : {total_cons:10.3f}\n"
                f"Net kWh  : {net:11.3f}\n"
                f"Efficiency: {max(0, efficiency):8.3f} %"
            )
            self.text_info.set_text(info_text)

        artists = [self.line_power, self.line_solar, self.line_rpm,
                   self.line_def, self.line_plasma,
                   self.attack_scatter, self.text_info]
        return artists

    def run(self):
        print(" [JAXA] Starting continuous scrolling animation... Press Ctrl+C to stop.\n")
        self.anim = FuncAnimation(
            self.fig,
            self.update_frame,
            frames=None,
            interval=30,
            blit=True,
            repeat=False,
            cache_frame_data=False
        )
        plt.show()

    def close(self):
        self.csv_file.close()
        plt.close(self.fig)
        print("\n" + "="*80)
        print(" FINAL ENGINEERING REPORT")
        print("="*80)
        print(f"  Total Energy Generated: {self.station.total_gen_kwh:.3f} kWh")
        print(f"  Total Energy Consumed:  {self.station.total_cons_kwh:.3f} kWh")
        print(f"  Net Balance:            {self.station.total_gen_kwh - self.station.total_cons_kwh:.3f} kWh")
        print(f"  Plasma Consumption:     {self.station.plasma_consumed_kwh:.3f} kWh")
        print(f"  Final RPM:              {self.station.rpm:.3f} RPM")
        print(f"  Stored Energy:          {self.station.stored_kwh:.3f} kWh")
        print(f"  Cyber Attacks Blocked:  {self.station.honeypot_attacks}")
        print("="*80)
        print("  TELEMETRY LOG: jaxa_v34_scroll.csv")
        print("="*80)


# ============================================================
# 3. MAIN
# ============================================================
if __name__ == "__main__":
    print("\n" + "="*80)
    print(" JAXA/MHI PRECISION CURSOR DASHBOARD v34.0 (CONTINUOUS STREAMING)")
    print(" ENGINEERED FOR TOKYO REVIEW BOARD")
    print("="*80)
    print(" [JAXA] Infinite scrolling X‑axis – old data exits left, new enters right.")
    print(" [JAXA] Sharp, sudden vertical movements (random walk).")
    print(" [JAXA] Side panel updates with 3‑decimal precision.")
    print(" [JAXA] Press Ctrl+C to stop.\n")

    station = SpacePowerStation(area=1000.0, demand=500.0)
    dashboard = PrecisionCursorDashboard(station, speed_factor=150.0, window_hours=1.0)
    try:
        dashboard.run()
    except KeyboardInterrupt:
        print("\n [JAXA] Animation stopped by user.")
    finally:
        dashboard.close()
