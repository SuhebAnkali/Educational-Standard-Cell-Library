# Educational Standard Cell Library Development

**Technologies:** Ngspice | SKY130 PDK | Yosys | OpenSTA | Python

## Overview
This repository explores the development and characterization of an educational CMOS standard-cell library.

The project focuses on understanding transistor-level circuit behavior, extracting timing and power information, and studying standard-cell library formats used in digital ASIC design flows.

## Objectives
- Design and characterize fundamental CMOS standard cells.
- Understand standard-cell timing models.
- Explore Liberty (.lib) file structure.
- Study timing and power characterization.
- Understand Static Timing Analysis (STA).
- Explore the relationship between SPICE characterization and digital implementation flows.

## Standard Cells
- Inverter (INV)
- 2-Input NAND (NAND2)
- 2-Input NOR (NOR2)
- 2-Input XOR (XOR2)
- D Flip-Flop (DFF)

## Characterization Parameters
- Cell Propagation Delay
- Rise and Fall Transition Time
- Setup Time
- Hold Time
- Input Capacitance
- Output Drive Characteristics
- Internal Power
- Leakage Power

## Standard Cell Library Concepts
- Liberty (.lib) format
- Timing arcs
- NLDM timing models
- Standard-cell characterization
- Setup and hold constraints
- Static Timing Analysis

## Tools and Technologies

| Tool | Purpose |
|---|---|
| Ngspice | Transistor-level simulation |
| SKY130 PDK | CMOS device models |
| Yosys | RTL synthesis |
| OpenSTA | Static Timing Analysis |
| Python | Automation and data processing |

## Design Flow
1. CMOS transistor-level circuit design.
2. SPICE simulation.
3. Timing and power characterization.
4. Liberty timing model exploration.
5. RTL synthesis using Yosys.
6. Static Timing Analysis using OpenSTA.

## Learning Outcomes
- Standard-cell library architecture.
- CMOS timing and power characterization.
- Liberty library fundamentals.
- Digital synthesis concepts.
- Static Timing Analysis.
- ASIC design flow fundamentals.

## References
- [SkyWater SKY130 PDK](https://github.com/google/skywater-pdk)
- [Yosys](https://github.com/YosysHQ/yosys)
- [OpenSTA](https://github.com/The-OpenROAD-Project/OpenSTA)
- [Ngspice](https://github.com/ngspice/ngspice)
- [Original project/reference](https://github.com/vsdip/vsdStdCellCharacterizer_sky130)

## Disclaimer
This repository is intended for educational and research purposes. Original project contributors and licenses must be acknowledged. Independently generated characterization data and modifications should be documented accurately.
