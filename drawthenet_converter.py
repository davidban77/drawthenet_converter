#!/usr/bin/env python
"""
drawthe.net to GNS3:

Python script that reads a drawthe.net topology file and builds the lab on GNS3 server
using gns3fy:

./drawthenet_converter.py --topology topology.yml
"""
import sys
import yaml
import time

from typing import Dict, Any, List
from argparse import ArgumentParser, Namespace
from gns3fy import Gns3Connector, Project, Node
from tabulate import tabulate

VERSION = "0.1.0"


def heading(message):
    """
    Returns a heading style text
    """
    header = f" {message} ".center(70, "#")
    return f"\n{header}\n"


def parsed_x(x: int, obj_width: int = 100) -> int:
    """
    Returns a coordinate `x` value that takes into account object width
    """
    return x * obj_width


def parsed_y(y: int, obj_height: int = 100) -> int:
    """
    Returns a coordinate `y` value that takes into account object height and is inverted
    """
    return (y * obj_height) * -1


def load_yaml(yaml_file: str) -> Dict[str, Any]:
    """
    Returns Python data structure derived from YAML file
    """
    with open(yaml_file, "r") as f:
        data = yaml.safe_load(f)
    return data


def get_nodes_spec(icons_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Parses the `icons` section from the drawthe.net YAML file to get the device
    information.

    The keys each device defined in the section must have:

    - `gns3_template`: Name of the GNS3 template where the device will be mapped into.
    - `x`: The `x` coordinate value.
    - `y`: The `y` coordinate value.

    NOTE: The coordinates DO NOT SUPPORT the `+1` or `-1` reference values that are
    available on drawthe.net
    """
    try:
        return [
            dict(
                name=device,
                template=params["gns3_template"],
                x=params["x"],
                y=params["y"],
            )
            for device, params in icons_data.items()
        ]
    except KeyError as err:
        raise ValueError(
            f"Parameter could not be found in the YAML icons section: {err}"
        )


def get_links_spec(connections_data: List[Dict[str, Any]]) -> List[List[str]]:
    """
    Parses the `connections` section from the drawthe.net YAML file to get the links
    information.

    Each entry must have the following key:

    - `endpoints`: List of link specification with the devices and port separated by `:`

    [<device_A>:<port_A>, <device_B>:<port_B>]
    """
    try:
        return [
            connection["endpoints"][0].split(":")
            + connection["endpoints"][-1].split(":")
            for connection in connections_data
        ]
    except Exception as err:
        raise ValueError(f"{err}\nCould not parse the links on the connection section")


def parse_args() -> Namespace:
    """
    Returns parsed arguments from CLI
    """
    parser = ArgumentParser(
        description="Reads drawthe.net topology file and creates GNS3 Topology"
    )
    parser.add_argument("-V", "--version", action="version", version=VERSION)
    parser.add_argument(
        "-v", "--verbosity", action="count", help="Increase output verbosity", default=0
    )
    parser.add_argument(
        "-t", "--topology", required=True, help="YAML/drawthe.net topology file.",
    )
    parser.add_argument(
        "-s", "--server", required=True, help="The GNS3 server address.",
    )
    parser.add_argument(
        "--port", required=False, help="The GNS3 server API port.", default=3080,
    )
    parser.add_argument(
        "--protocol",
        required=False,
        help="Protocol to use to connect.",
        default="http",
        choices=["http", "https"],
    )
    args, unk = parser.parse_known_args()
    return args


def main():
    # Parse the arguments
    args = parse_args()
    topology_data = load_yaml(args.topology)

    # Collect lab name
    print(heading("Collecting topology data"))
    lab_name: str = topology_data["title"]["text"]
    print(f"The lab name would be: {lab_name}")

    # Collect nodes specs
    nodes_spec = get_nodes_spec(topology_data["icons"])

    # Collect connections specs
    links_spec = get_links_spec(topology_data["connections"])

    # Create Gns3Connector
    print(heading(f"Configuring lab on GNS3 server"))
    server = Gns3Connector(f"{args.protocol}://{args.server}:{args.port}")

    # Verify lab is not already created
    lab_project = server.get_project(name=lab_name)
    if lab_project:
        delete_lab = input(f"\nLab already created, do you want to delete it? (y/n): ")
        if delete_lab == "y":
            server.delete_project(lab_project["project_id"])
        else:
            sys.exit("Exiting...")

    # Create the lab
    lab = Project(name=lab_name, connector=server)
    lab.create()
    print(f"Project created: {lab.name}\n")

    # Create the nodes
    for device in nodes_spec:
        node = Node(
            project_id=lab.project_id,
            connector=server,
            name=device["name"],
            template=device["template"],
            x=parsed_x(device["x"] - 10),
            y=parsed_y(device["y"] - 5),
        )
        node.create()
        time.sleep(3)
        print(f"Device created: {node.name}")

    # Create the links
    for link in links_spec:
        lab.create_link(*link)

    # Summary
    print(heading("Nodes Summary"))
    nodes_summary: str = lab.nodes_summary(is_print=False)
    print(tabulate(nodes_summary, headers=["Device", "Status", "Console Port", "ID"]))
    print(heading("Links Summary"))
    links_summary: str = lab.links_summary(is_print=False)
    print(tabulate(links_summary, headers=["Device A", "Port A", "Device B", "Port B"]))

    return


if __name__ == "__main__":
    main()
