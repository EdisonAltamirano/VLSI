import os
import numpy as np
import argparse
import math
import time
import interstellar as cm
import datetime
import json


def basic_optimizer(
    arch_info, network_info, schedule_info=None, basic=False, verbose=False
):

    resource = cm.Resource.arch(arch_info)
    layer = cm.Layer.layer(network_info)
    schedule = cm.Schedule.schedule(schedule_info) if schedule_info != None else None
    smallest_cost, best_mapping_point, perf = cm.optimizer.opt_optimizer(
        resource, layer, schedule, verbose
    )

    level_costs = cm.cost_model.get_cost(resource, best_mapping_point, layer, verbose)
    # if verbose or basic:
    if not verbose:
        print("Optimal_Energy_(pJ): ", smallest_cost)

    # print("Cost for Each Level (pJ): ", level_costs) #TODO
    print("Best_Schedule_(innermost_loop_to_outermost_loop): ")
    cm.utils.print_best_schedule(best_mapping_point)

    return smallest_cost, perf


def mem_explore_optimizer(arch_info, network_info, schedule_info, verbose=False):

    assert "explore_points" in arch_info, "missing explore_points in arch file"
    assert "capacity_scale" in arch_info, "missing capacity_scale in arch file"
    assert "access_cost_scale" in arch_info, "missing access_cost_scale in arch file"
    cwd = os.getcwd()
    #    output_filename = os.path.join(cwd, "dataset", network_info['layer_name'] + '_128.csv')
    explore_points = arch_info["explore_points"]
    energy_list = np.zeros(tuple(explore_points))
    summary_array = np.zeros([np.product(explore_points), 12])
    # TODO support more than two levels of explorations
    capacity0 = arch_info["capacity"][0]
    capacity1 = arch_info["capacity"][1]
    cost0 = arch_info["access_cost"][0]
    cost1 = arch_info["access_cost"][1]
    i = 0
    for x in range(explore_points[0]):
        arch_info["capacity"][0] = capacity0 * (arch_info["capacity_scale"][0] ** x)
        arch_info["access_cost"][0] = cost0 * (arch_info["access_cost_scale"][0] ** x)
        for y in range(explore_points[1]):
            # if x == 0 and y < 1:
            #    continue
            arch_info["capacity"][1] = capacity1 * (arch_info["capacity_scale"][1] ** y)
            arch_info["access_cost"][1] = cost1 * (
                arch_info["access_cost_scale"][1] ** y
            )
            print(arch_info)
            energy, perf = basic_optimizer(
                arch_info, network_info, schedule_info, False, verbose
            )
            energy_list[x][y] = energy
            cur_point = (
                list(network_info["layer_info"])[:9]
                + arch_info["capacity"][:-1]
                + [energy]
            )
            summary_array[i] = cur_point
            #            np.savetxt(output_filename, summary_array, delimiter=",")
            i += 1

    print(list(energy_list))
    print("optimal energy for all memory systems: ", np.min(np.array(energy_list)))


def mac_explore_optimizer(arch_info, network_info, schedule_info, verbose=False):

    dataflow_res = []
    # TODO check the case when parallel count larger than layer dimension size
    dataflow_generator = dataflow_generator_function(arch_info)

    for dataflow in dataflow_generator:
        energy, perf = basic_optimizer(
            arch_info, network_info, schedule_info, False, verbose
        )
        dataflow_res.append[energy]

    if verbose:
        print("optimal energy for all dataflows: ", dataflow_res)

    return dataflow_res


def dataflow_explore_optimizer(arch_info, network_info, file_name, verbose=False):

    assert (
        arch_info["parallel_count"][0] > 1
    ), "parallel count has to be more than 1 for dataflow exploration"

    resource = cm.Resource.arch(arch_info)
    layer = cm.Layer.layer(network_info)
    dataflow_tb = cm.mapping_point_generator.dataflow_exploration(
        resource, layer, file_name, verbose
    )

    if verbose:
        print("dataflow table done ")


def mem_explore_optimizer_4_level(
    arch_info, network_info, schedule_info, verbose=False
):
    assert "explore_points" in arch_info, "missing explore_points in arch file"
    assert "capacity_scale" in arch_info, "missing capacity_scale in arch file"
    assert "access_cost_scale" in arch_info, "missing access_cost_scale in arch file"
    cwd = os.getcwd()
    #    output_filename = os.path.join(cwd, "dataset", network_info['layer_name'] + '_128.csv')
    explore_points = arch_info["explore_points"]
    energy_list = np.zeros(tuple(explore_points))
    summary_array = np.zeros([np.product(explore_points), 13])
    capacity0 = arch_info["capacity"][0]
    capacity1 = arch_info["capacity"][1]
    capacity2 = arch_info["capacity"][2]
    cost0 = arch_info["access_cost"][0]
    cost1 = arch_info["access_cost"][1]
    cost2 = arch_info["access_cost"][2]
    i = 0
    for x in range(explore_points[0]):
        arch_info["capacity"][0] = capacity0 * (arch_info["capacity_scale"][0] ** x)
        arch_info["access_cost"][0] = cost0 * (arch_info["access_cost_scale"][0] ** x)
        for y in range(explore_points[1]):
            arch_info["capacity"][1] = capacity1 * (arch_info["capacity_scale"][1] ** y)
            arch_info["access_cost"][1] = cost1 * (
                arch_info["access_cost_scale"][1] ** y
            )
            for z in range(explore_points[2]):
                arch_info["capacity"][2] = capacity2 * (
                    arch_info["capacity_scale"][2] ** z
                )
                arch_info["access_cost"][2] = cost2 * (
                    arch_info["access_cost_scale"][2] ** z
                )
                print(arch_info)

                # TODO: Calculate the area of the design
                # total_area = sum(area(MAC)) + sum(2 * area(register file)) + 2 * area(buffer)
                area = (
                    2
                    * (
                        arch_info["capacity"][0]
                        + arch_info["capacity"][1]
                        + arch_info["capacity"][2]
                    )
                    + 2 * arch_info["capacity"][3]
                ) / 1e9

                print("Area: ", area)
                if area > 2:
                    energy_list[x][y][z] = np.nan
                    print("INFO: Architecture does not fulfill area constraint.")
                    continue
                try:
                    energy, perf = basic_optimizer(
                        arch_info, network_info, schedule_info, False, verbose
                    )
                    energy_list[x][y][z] = energy
                    cur_point = (
                        list(network_info["layer_info"])[:9]
                        + arch_info["capacity"][:-1]
                        + [energy]
                    )
                    summary_array[i] = cur_point
                    #            np.savetxt(output_filename, summary_array, delimiter=",")
                    i += 1
                except Exception as e:
                    energy_list[x][y][z] = np.nan
                    print("WARNING: No valid mapping point found.")
                print("=" * 80)

    print(list(energy_list))
    print("optimal energy for all memory systems: ", np.nanmin(np.array(energy_list)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "type",
        choices=["basic", "mem_explore", "dataflow_explore", "mem_explore_4"],
        help="optimizer type",
    )
    parser.add_argument("arch", help="architecture specification")
    parser.add_argument("network", help="network specification")
    parser.add_argument("-s", "--schedule", help="restriction of the schedule space")
    parser.add_argument(
        "-n", "--name", default="dataflow_table", help="name for the dumped pickle file"
    )
    parser.add_argument("-v", "--verbose", action="count", help="vebosity")
    parser.add_argument(
        "-j",
        "--json_name",
        default="result.json",
        help="result json file name for basic search",
    )
    args = parser.parse_args()

    if args.json_name == "result.json":
        json_name = (
            "result_" + datetime.datetime.now().strftime("%m-%d_%H_%M_%S") + ".json"
        )
    else:
        json_name = args.json_name

    start = time.time()
    arch_info, network_info, schedule_info = cm.extract_input.extract_info(args)
    if args.type == "basic":
        energy, perf = basic_optimizer(
            arch_info, network_info, schedule_info, True, args.verbose
        )
        json_data = {}
        json_data["runtime"] = perf
        json_data["energy"] = energy
        json_data["file_arch"] = args.arch
        json_data["file_layer"] = args.network
        with open(json_name, "w") as jf:
            json.dump(json_data, jf)
    elif args.type == "mem_explore":
        mem_explore_optimizer(arch_info, network_info, schedule_info, args.verbose)
    elif args.type == "dataflow_explore":
        dataflow_explore_optimizer(arch_info, network_info, args.name, args.verbose)
    elif args.type == "mem_explore_4":
        mem_explore_optimizer_4_level(
            arch_info, network_info, schedule_info, args.verbose
        )
    end = time.time()
    print("Elapsed_Time_(s): ", round((end - start), 2))
