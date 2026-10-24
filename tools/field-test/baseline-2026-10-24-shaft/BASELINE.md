# Wichita baseline: shaft balcony, 50 Archbishop St (24 Oct 2026, 15:36-15:59 Malta time)

HackRF One (clone, fw 2026.01.3) on the Mac Mini, balcony antenna deep in the shaftway. 2 Msps, LNA 32, VGA 20, amp off. Narrowband recordings tuned 250 kHz above the target. Receive-only.

## Sweeps (peak above the median floor)
sweep_118-137MHz.csv floor -67.6 dB  top: 120.002 MHz +22, 119.978 MHz +18, 120.027 MHz +15, 118.410 MHz +7, 118.386 MHz +6, 119.032 MHz +6, 121.420 MHz +6, 119.057 MHz +6
sweep_156-163MHz.csv floor -69.8 dB  top: 159.993 MHz +15, 160.017 MHz +14, 159.968 MHz +7, 161.983 MHz +6, 161.386 MHz +5, 163.226 MHz +5, 164.271 MHz +4, 166.336 MHz +4
sweep_430-447MHz.csv floor -71.3 dB  top: 439.988 MHz +6, 444.366 MHz +4, 440.012 MHz +4, 442.226 MHz +4, 445.336 MHz +4, 440.958 MHz +4, 447.077 MHz +3, 445.162 MHz +3
sweep_860-870MHz.csv floor -72.0 dB  top: 878.122 MHz +18, 873.744 MHz +18, 873.769 MHz +15, 878.147 MHz +15, 878.097 MHz +12, 873.719 MHz +9, 879.988 MHz +6, 860.012 MHz +5

## Channels (SNR within 8 kHz of target vs. nearby noise; active = share of frames over 6 dB)
FM92.7       92.7000 MHz  peak SNR  10.4 dB  median  5.3 dB  active  38%
CH16        156.8000 MHz  peak SNR   4.3 dB  median  1.5 dB  active   0%
CH69        156.4750 MHz  peak SNR   4.2 dB  median  1.4 dB  active   0%
CH12        156.6000 MHz  peak SNR  32.3 dB  median 32.0 dB  active 100%
CH14        156.7000 MHz  peak SNR   4.1 dB  median  1.6 dB  active   0%
CH10        156.5000 MHz  peak SNR   5.4 dB  median  1.6 dB  active   0%
CH09        156.4500 MHz  peak SNR   4.1 dB  median  1.5 dB  active   0%
CH11        156.5500 MHz  peak SNR   4.5 dB  median  1.4 dB  active   0%
CH06        156.3000 MHz  peak SNR   4.2 dB  median  1.4 dB  active   0%
CH13        156.6500 MHz  peak SNR   4.5 dB  median  1.4 dB  active   0%
CH72        156.6250 MHz  peak SNR   4.2 dB  median  1.4 dB  active   0%
CH77        156.8750 MHz  peak SNR   4.5 dB  median  1.4 dB  active   0%
AIS1        161.9750 MHz  peak SNR  24.6 dB  median  1.4 dB  active   1%
AIS2        162.0250 MHz  peak SNR   6.4 dB  median  1.5 dB  active   0%
TWR1        135.1050 MHz  peak SNR   4.1 dB  median  1.2 dB  active   0%
TWR2        133.9050 MHz  peak SNR   4.8 dB  median  1.9 dB  active   0%
APP1        128.1550 MHz  peak SNR   4.4 dB  median  1.3 dB  active   0%
APP2        118.3550 MHz  peak SNR   5.0 dB  median  1.9 dB  active   0%
GND         121.6050 MHz  peak SNR   4.6 dB  median  1.7 dB  active   0%
ATIS1       127.0050 MHz  peak SNR   4.6 dB  median  1.6 dB  active   0%
ATIS2       127.4050 MHz  peak SNR   5.2 dB  median  1.5 dB  active   0%
GUARD       121.5000 MHz  peak SNR   4.2 dB  median  1.0 dB  active   0%
CTL1        127.5250 MHz  peak SNR   4.5 dB  median  1.7 dB  active   0%
CTL2        122.7750 MHz  peak SNR   4.5 dB  median  1.4 dB  active   0%
CTL3        130.9750 MHz  peak SNR   4.0 dB  median  1.2 dB  active   0%
R2m1        145.6250 MHz  peak SNR   4.4 dB  median  1.8 dB  active   0%
R2m2        145.7000 MHz  peak SNR   4.3 dB  median  1.4 dB  active   0%
R2m3        145.7500 MHz  peak SNR   4.4 dB  median  1.2 dB  active   0%
R2m4        145.4750 MHz  peak SNR   4.9 dB  median  1.9 dB  active   0%
R70a        430.8750 MHz  peak SNR   4.4 dB  median  1.5 dB  active   0%
R70b        430.9250 MHz  peak SNR   4.3 dB  median  1.4 dB  active   0%
R70c        433.1750 MHz  peak SNR   4.7 dB  median  1.5 dB  active   0%
R70d        438.6500 MHz  peak SNR   4.5 dB  median  1.5 dB  active   0%
PMR446      446.1000 MHz  peak SNR   4.5 dB  median  1.5 dB  active   0%
CB27         27.1850 MHz  peak SNR   8.1 dB  median  5.8 dB  active  42%

## LoRa 868 (5 min, centred 868.85)
Meshtastic LongFast 869.525  bursts   0  time active  0.0%  peak +1.6 dB
LoRaWAN 868.1                bursts   0  time active  0.0%  peak +2.2 dB
LoRaWAN 868.3                bursts   0  time active  0.0%  peak +2.2 dB
LoRaWAN 868.5                bursts   0  time active  0.0%  peak +2.1 dB
867.9                        bursts   0  time active  0.0%  peak +2.3 dB
duration 300 s

Notes: AIS1 bursts at +24.6 dB, likely real AIS. CH12 is a constant carrier, probably interference. Round-number spurs (120.000, 160.000, 440.000 MHz) come from local hardware. The ISM433 burst count is inconclusive (crude any-bin threshold, peak +13.6 dB at 433.649). CB27 is 42% active at about 8 dB, probably noise (the HackRF is weak at 27 MHz).
