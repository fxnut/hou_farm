import os
import imp
import re
import hashlib
import subprocess

try:
    import hou
except:
    pass

import hou_farm.tools as hou_farm_tools

from hou_farm.integersequence import IntegerSequence
from hou_farm.errors import RopErrorList, RopInfoMessage, RopWarningMessage, RopErrorMessage, ErrorList, ErrorMessage

# --------------------------------------------------------------------------
# Farm Communication
# --------------------------------------------------------------------------


def validate_environment(error_list_obj):
    """
    Standard callback that must exist for each farm implementation.
    Validates the current environment for the farm and returns a list of errors (or empty list if none)
    Returns:
        List: A list of strings containing error messages to be displayed to the user. 
              List will be empty on successful validation.
    """
    error_list_obj = ErrorList(error_list_obj)

    result = None
    try:
        result = get_deadline_command_string()
    except KeyError:
        pass
    if result is None:
        error_list_obj.add(ErrorMessage("Cannot find Deadline installation. \n"
                                        "For Windows, please check DEADLINE_PATH environment variable is set.\n"
                                        "For OSX, '/Users/Shared/Thinkbox/DEADLINE_PATH' must exist"))
        return False
        
    return True


def get_deadline_command_string():
    """
    Retrieves the Deadline/bin path and the Deadline executable path.
    
    If HOUFARM_VIRTUAL_DEADLINE is set, then it returns empty strings in the tuple.

    Returns:
        Tuple Pair: First element is a string containing the Deadline/bin path, 
                    the second element is a string containing the path to the executable.
    """

    # Setting HOUFARM_VIRTUAL_DEADLINE as an environment variable allows you to run and test Hou Farm without having Deadline installed
    if "HOUFARM_VIRTUAL_DEADLINE" in os.environ:
        return ["",""]

    # On OSX, we look for the DEADLINE_PATH file. On other platforms, we use the environment variable.
    if os.path.exists("/Users/Shared/Thinkbox/DEADLINE_PATH"):
        with file("/Users/Shared/Thinkbox/DEADLINE_PATH") as f:
            deadline_bin = f.read().strip()
        return deadline_bin, os.path.join(deadline_bin, "deadlinecommand")
    else:
        deadline_bin = os.environ['DEADLINE_PATH']
        if os.name == 'nt':
            return deadline_bin, os.path.join(deadline_bin, "deadlinecommand.exe")
        else:
            return deadline_bin, os.path.join(deadline_bin, "deadlinecommand")    


def call_virtual_deadline_command(arguments, background=True, read_stdout=True):
    cmd = arguments[0]
    if cmd == "-selectmachinelist":
        hou.ui.displayMessage("\"Select Machine List\" Dialog."
            "\n\nYou're seeing this message box because Deadline Virtual mode is currently enabled.\nHOUFARM_VIRTUAL_DEADLINE is set.",("OK",), hou.severityType.Message)
        return "machine1 \nmachine2 \nmachine3"
    elif cmd == "-selectlimitgroups":
        hou.ui.displayMessage("\"Select Limit Group List\" Dialog."
            "\n\nYou're seeing this message box because Deadline Virtual mode is currently enabled.\nHOUFARM_VIRTUAL_DEADLINE is set.",("OK",), hou.severityType.Message)
        return "group1 \ngroup2 \ngroup3"
    elif cmd == "-selectdependencies":
        hou.ui.displayMessage("\"Select Job Dependency List\" Dialog."
            "\n\nYou're seeing this message box because Deadline Virtual mode is currently enabled.\nHOUFARM_VIRTUAL_DEADLINE is set.",("OK",), hou.severityType.Message)
        return "123 456 789"
    elif cmd == "-getmaximumpriority":
        return 100
    elif cmd == "-pools":
        return "none \npool1 \npool2\n pool3"
    elif cmd == "-groups":
        return "none \ngroup1 \ngroup2 \ngroup3"
    elif cmd == "-GetCurrentUserHomeDirectory":
        return os.environ["HOME"]

    hou.ui.displayMessage("Unsupported Virtual Deadline Command."
        "\n\nYou're seeing this message box because Deadline Virtual mode is currently enabled.\nHOUFARM_VIRTUAL_DEADLINE is set.",("OK",), hou.severityType.Message)


def call_deadline_command(arguments, background=True, read_stdout=True):
    """
    Calls the Deadline command line tool with arguments and returns the output
    Taken from deadline8_repo\submission\Houdini\Main\SubmitHoudiniToDeadline.py
    Some minor modifications have been made for formatting

    If HOUFARM_VIRTUAL_DEADLINE is set, then calls are forwarded to call_virtual_deadline_command() instead.

    Args:
        arguments (list): A list of strings to pass to the deadline command as arguments
        background (bool): True to run the process in the background, False to run as a blocking process
        read_stdout (bool): True to read the result from stdout

    Returns:
        String: Output from calling deadline's command
    """

    # Setting HOUFARM_VIRTUAL_DEADLINE as an environment variable allows you to run and test Hou Farm without having Deadline installed
    if "HOUFARM_VIRTUAL_DEADLINE" in os.environ:
        return call_virtual_deadline_command(arguments, background, read_stdout)

    deadline_bin, deadline_command = get_deadline_command_string()

    startupinfo = None
    creation_flags = 0
    if os.name == 'nt':
        if background:
            # Python 2.6 has subprocess.STARTF_USESHOWWINDOW, and Python 2.7 has
            # subprocess._subprocess.STARTF_USESHOWWINDOW, so check for both.
            if hasattr(subprocess, '_subprocess') and hasattr(subprocess._subprocess, 'STARTF_USESHOWWINDOW'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess._subprocess.STARTF_USESHOWWINDOW
            elif hasattr(subprocess, 'STARTF_USESHOWWINDOW'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        else:
            # still show top-level windows, but don't show a console window
            CREATE_NO_WINDOW = 0x08000000   # MSDN process creation flag
            creation_flags = CREATE_NO_WINDOW

    arguments.insert(0, deadline_command)

    stdout_pipe = None
    if read_stdout:
        stdout_pipe = subprocess.PIPE

    # Specifying PIPE for all handles to workaround a Python bug on Windows.
    # The unused handles are then closed immediately afterwards.
    proc = subprocess.Popen(arguments, cwd=deadline_bin, stdin=subprocess.PIPE, stdout=stdout_pipe,
                            stderr=subprocess.PIPE, startupinfo=startupinfo, creationflags=creation_flags)
    proc.stdin.close()
    proc.stderr.close()

    output = ""
    if read_stdout:
        output = proc.stdout.read()
    return output


def select_deadline_machine_list(cur_value):
    """
    Show the Deadline GUI for selecting farm machines

    Args:
        cur_value (str): Current list of machines to show selected in the dialog

    Returns:
        String: A space separated list of machine names
    """
    output = call_deadline_command(["-selectmachinelist", cur_value], False)
    output = output.replace("\r", "").replace("\n", "")
    if output == "Action was cancelled by user":
        output = None
    return output


def select_deadline_limit_groups(cur_value):
    """
    Show the Deadline GUI for selecting limit groups

    Args:
        cur_value (str): Current list of groups to show selected in the dialog

    Returns:
        String: A space separated list of group names
    """
    output = call_deadline_command(["-selectlimitgroups", cur_value], False)
    output = output.replace("\r", "").replace("\n", "")
    if output == "Action was cancelled by user":
        output = None
    return output


def select_deadline_dependencies(cur_value):
    """
    Show the Deadline GUI for selecting job dependencies

    Args:
        cur_value (str): Current list of dependencies to show selected in the dialog (if supported)

    Returns:
        String: A space separated list of job IDs
    """
    output = call_deadline_command(["-selectdependencies", cur_value], False)
    output = output.replace("\r", "").replace("\n", "")
    if output == "Action was cancelled by user":
        output = None
    return output


# --------------------------------------------------------------------------
# Global Farm State
# --------------------------------------------------------------------------


class DeadlineGlobals(object):
    def __init__(self):
        self.max_priority = 100
        self.pools = []
        self.groups = []
        self.home_dir = ""


def get_global_data():
    """
    Retrieve and cache global data for the Deadline environment so that we can speedily populate comboboxes for
    the various Deadline options like Pools and Groups.

    Returns:
        DeadlineGlobals: An instance of DeadlineGlobals containing global Deadline data
    """

    if not hasattr(hou.session, "hou_farm_deadline_data") or hou.session.hou_farm_deadline_data is None:
        deadline_globals = DeadlineGlobals()
        with hou.InterruptableOperation("Gathering Deadline data...", open_interrupt_dialog=True) as operation:

            count = 0.0
            task_count = 4.0

            try:
                output = call_deadline_command(["-getmaximumpriority", ])
                deadline_globals.max_priority = int(output)
            except (hou.OperationFailed, ValueError):
                deadline_globals.max_priority = 100

            count += 1.0
            try:
                operation.updateProgress(count/task_count)
            except hou.OperationFailed:
                pass

            # Get pools
            output = call_deadline_command(["-pools", ])
            deadline_globals.pools = output.splitlines()

            count += 1.0
            try:
                operation.updateProgress(count/task_count)
            except hou.OperationFailed:
                pass

            # Get groups
            output = call_deadline_command(["-groups", ])
            deadline_globals.groups = output.splitlines()

            count += 1.0
            try:
                operation.updateProgress(count/task_count)
            except hou.OperationFailed:
                pass

            # Get user's Deadline home directory
            output = call_deadline_command(["-GetCurrentUserHomeDirectory", ])
            deadline_globals.home_dir = output.replace("\r", "").replace("\n", "")

            count += 1.0
            try:
                operation.updateProgress(count/task_count)
            except hou.OperationFailed:
                pass

        hou.session.hou_farm_deadline_data = deadline_globals

    return hou.session.hou_farm_deadline_data


# --------------------------------------------------------------------------
# Menu GUI Callbacks
# --------------------------------------------------------------------------


def pool_menu_callback(script_args):
    """
    GUI callback for populating the Pools combobox

    Args:
        script_args (dict): The Houdini "kwargs" dictionary

    Returns:
        List: A name value paired list required by Houdini for passing to a combobox
    """
    deadline_globals = get_global_data()
    if len(deadline_globals.pools) == 0:
        return ["", ""]
    menu = [pool for pool in deadline_globals.pools for i in xrange(2)]
    return menu


def group_menu_callback(script_args):
    """
    GUI callback for populating the Groups combobox

    Args:
        script_args (dict): The Houdini "kwargs" dictionary

    Returns:
        List: A name value paired list required by Houdini for passing to a combobox
    """
    deadline_globals = get_global_data()
    if len(deadline_globals.groups) == 0:
        return ["", ""]
    menu = [group for group in deadline_globals.groups for i in xrange(2)]
    return menu


# --------------------------------------------------------------------------
# Deadline GUI Callbacks
# --------------------------------------------------------------------------


def select_deadline_machine_list_callback(script_args):
    """
    GUI callback to select machines and set the appropriate parameter. It is designed to be able to be used by
    multiple parameter & button pairs. To do this, it assumes that the button has the same name as the target parm
    but with "_browse_button" on the end

    Args:
        script_args (dict): The Houdini "kwargs" dictionary

    Returns:
        None
    """
    rop_node = script_args["node"]
    target_parm_name = script_args["script_parm"].replace("_browse_button", "")
    target_parm = rop_node.parm(target_parm_name)
    result = select_deadline_machine_list(target_parm.eval())
    if result is not None:
        target_parm.set(result)


def select_deadline_limits_callback(script_args):
    """
    GUI callback to select limits and set the appropriate parameter. It is designed to be able to be used by
    multiple parameter & button pairs. To do this, it assumes that the button has the same name as the target parm
    but with "_browse_button" on the end

    Args:
        script_args (dict): The Houdini "kwargs" dictionary

    Returns:
        None
    """
    rop_node = script_args["node"]
    target_parm_name = script_args["script_parm"].replace("_browse_button", "")
    target_parm = rop_node.parm(target_parm_name)
    result = select_deadline_limit_groups(target_parm.eval())
    if result is not None:
        target_parm.set(result)


def select_deadline_dependencies_callback(script_args):
    """
    GUI callback to select dependencies and set the appropriate parameter. It is designed to be able to be used by
    multiple parameter & button pairs. To do this, it assumes that the button has the same name as the target parm
    but with "_browse_button" on the end

    Args:
        script_args (dict): The Houdini "kwargs" dictionary

    Returns:
        None
    """
    rop_node = script_args["node"]
    target_parm_name = script_args["script_parm"].replace("_browse_button", "")
    target_parm = rop_node.parm(target_parm_name)
    result = select_deadline_dependencies(target_parm.eval())
    if result is not None:
        target_parm.set(result)


# --------------------------------------------------------------------------
# Button GUI Callbacks
# --------------------------------------------------------------------------


def refresh_deadline_data_button_callback(script_args):
    """
    GUI callback to update the global Deadline data.

    Args:
        script_args (dict): The Houdini "kwargs" dictionary

    Returns:
        None
    """
    hou.session.hou_farm_deadline_data = None
    get_global_data()


def submit_branch_button_callback(script_args):
    """
    GUI callback to submit the node and its dependents to the farm.
    If "hf_validate_only" parameter is set to True then it won't submit; it will only do the validation stage.
    Validation is only done for this node and its dependents.

    Args:
        script_args (dict): The Houdini "kwargs" dictionary

    Returns:
        None
    """
    with RopErrorList(None) as error_list_obj:

        rop_node = script_args["node"]
        validate_only = rop_node.parm("hf_validate_only").eval() == 1

        rop_list = hou_farm_tools.get_rop_process_list(rop_node, False)
        submit_rop_list(rop_list, validate_only, error_list_obj)


def submit_node_button_callback(script_args):
    """
    GUI callback to submit only this node to the farm. No other dependent nodes will be submitted.
    If "hf_validate_only" parameter is set to True then it won't submit; it will only do the validation stage.
    Validation is only done for this node.

    Args:
        script_args (dict): The Houdini "kwargs" dictionary

    Returns:
        None
    """

    with RopErrorList(None) as error_list_obj:

        rop_node = script_args["node"]
        validate_only = rop_node.parm("hf_validate_only").eval() == 1

        submit_rop_list([rop_node], validate_only, error_list_obj)


def submit_tree_button_callback(script_args):
    """
    GUI callback to submit this node and all connected nodes (above, below and side branches) to the farm.
    If "hf_validate_only" parameter is set to True then it won't submit; it will only do the validation stage.
    Validation is only done for all submitted nodes.

    Args:
        script_args (dict): The Houdini "kwargs" dictionary

    Returns:
        None
    """
    with RopErrorList(None) as error_list_obj:

        rop_node = script_args["node"]
        validate_only = rop_node.parm("hf_validate_only").eval() == 1

        rop_list = hou_farm_tools.get_rop_process_list(rop_node, True)
        submit_rop_list(rop_list, validate_only, error_list_obj)


# --------------------------------------------------------------------------
# Job Submission
# --------------------------------------------------------------------------


def integer_sequence_from_deadline_range_spec(range_spec_str):
    """
    Converts Deadline's varied frame syntax into an instance of the IntegerSequence class.

    Args:
        range_spec_str (str): A string containing a frame sequence in one of Deadline's valid formats

    Returns:
        IntegerSequence: An instance of IntegerSequence class that represents the supplied frame ranges
    """

    # Remove spaces and make sure range specs are separated by commas
    range_spec_str = re.sub(" ", ",", range_spec_str)
    range_spec_str = re.sub(",+", ",", range_spec_str)

    # Ensure that we always have a colon for the step value
    range_spec_str = re.sub("x|step|by|every", ":", range_spec_str)

    # Ensure that we only have one colon and it's only ever used as the step
    range_spec_list = range_spec_str.split(",")
    for i in xrange(len(range_spec_list)):
        pos = range_spec_list[i].find(":")
        rpos = range_spec_list[i].rfind(":")
        if pos != -1 and pos != rpos:
            range_spec_list[i] = range_spec_list[i][:pos] + "-" + range_spec_list[i][pos+1:]
    range_spec_str = ",".join(range_spec_list)

    # Everything should now be in the following format so that we can create the IntegerSequence
    # "1,2,3,4-10,13,15-30:5"

    return IntegerSequence.from_string(range_spec_str)


def write_job_files(plugin_name, job_index, job_parm_dict, plugin_parm_dict):
    """
    Writes Deadline job and plugin files to Deadline temp folder ready for submission.
    This mimics the way Thinkbox write their submitters and also uses an incrementing job_index method to avoid file
    clashes. This is far from foolproof and could be improved on.

    If HOUFARM_VIRTUAL_DEADLINE is defined then filenames are constructed, but no files are written.

    Args:
        plugin_name (str): Name of the plugin being submitted: "Mantra" for renders and "Houdini" for everything else
        job_index (int): Unique job index to ensure files don't overwrite each other
        job_parm_dict (dict): Key value pairs to write to the job file
        plugin_parm_dict (dict): Key value pairs to write to the plugin file

    Returns:
        (String, String): A tuple containing the filenames of the job and plugin submission files respectively
    """
    deadline_globals = get_global_data()
    job_filename = os.path.join(deadline_globals.home_dir, "temp",
                                "{0}_submit_info{1}.job".format(plugin_name, job_index))
    
    # Setting HOUFARM_VIRTUAL_DEADLINE as an environment variable allows you to run and test Hou Farm without having Deadline installed
    if "HOUFARM_VIRTUAL_DEADLINE" not in os.environ:
        file_handle = open(job_filename, "w")

        for key, value in job_parm_dict.iteritems():
            file_handle.write("{0}={1}\n".format(key, value))
        file_handle.close()

    plugin_filename = os.path.join(deadline_globals.home_dir, "temp",
                                   "{0}_plugin_info{1}.job".format(plugin_name, job_index))
    
    if "HOUFARM_VIRTUAL_DEADLINE" not in os.environ:
        file_handle = open(plugin_filename, "w")

        for key, value in plugin_parm_dict.iteritems():
            file_handle.write("{0}={1}\n".format(key, value))
        file_handle.close()
    
    return job_filename, plugin_filename


def submit_job_files_to_deadline(job_filename, plugin_filename, submit_scene):
    """
    Performs the actual job submission to Deadline.
    If HOUFARM_VIRTUAL_DEADLINE is defined, then it will return a unique dummy job id for testing.

    Args:
        job_filename (str): The filename of the job file
        plugin_filename (str): The filename of the plugin file
        submit_scene (bool): If True submits the scene file to Deadline, otherwise Deadline references the original file

    Returns:
        String: The job id. Can be used to set up dependencies with other jobs
    """
    arguments = [job_filename, plugin_filename]
    if submit_scene:
        arguments.append(hou.hipFile.path())

    # Setting HOUFARM_VIRTUAL_DEADLINE as an environment variable allows you to run and test Hou Farm without having Deadline installed
    if "HOUFARM_VIRTUAL_DEADLINE" in os.environ:
        md5_encoder = hashlib.md5()
        job_id = md5_encoder.update("".join(arguments))
    else:
        job_result = call_deadline_command(arguments)
        job_id = ""
        result_array = job_result.split("\n")
        for line in result_array:
            if line.startswith("JobID="):
                job_id = line.replace("JobID=", "")
                job_id = job_id.strip()
                break
    return job_id


def submit_rop_list(rop_list, validate_only, error_list_obj=None):
    """
    Submits a list of ROPs to Deadline. Performs a validation check before submission.

    Args:
        rop_list (list of hou.RopNode): A list of ROPs to submit
        validate_only (bool): If set to True, it will only validate the nodes and no submission will happen.
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        None
    """
    with RopErrorList(error_list_obj) as error_list_obj:

        validate_rop_list(rop_list, error_list_obj)

        progress_message = "Submitting to Deadline..."

        if validate_only:
            progress_message = "Validating..."
            error_list_obj.add_to_front(RopWarningMessage(None, "VALIDATION MODE. Job will not be submitted"))
        else:
            if error_list_obj.error_count() != 0:
                error_list_obj.display()
                return
            elif error_list_obj.warning_count() != 0:
                if error_list_obj.display(options=("Submit Anyway", "Cancel")) == 1:
                    return

            if hou.hipFile.hasUnsavedChanges():
                result = hou.ui.displayMessage("The scene has unsaved changes. "
                                               "Press OK to save and continue with submission.",
                                               ("OK", "Cancel"), hou.severityType.Message)
                if result == 1:
                    return

                hou.hipFile.save()

        job_id_dict = {}
        batch_name = hou.hipFile.basename()
        job_index = 0

        count = 1.0
        task_count = float(len(rop_list))
        with hou.InterruptableOperation(progress_message, open_interrupt_dialog=True) as operation:
            for rop_node in rop_list:
                dependency_list = []
                for input_rop in rop_node.inputs():
                    if input_rop in rop_list:
                        try:
                            job_id = job_id_dict[input_rop.path()]
                        except KeyError:
                            hou.ui.displayMessage("Problem with resolving dependency order during submission.\n"
                                                  "Job only partially submitted.\n"
                                                  "Problem during submission for "+rop_node.path()+"\n"
                                                  "Could not find job ID for "+input_rop.path(), ("OK",),
                                                  hou.severityType.Error)
                            return
                        dependency_list.append(job_id)

                submit_func_name = "submit_node_{0}_{1}".format(hou_farm_tools.get_rop_context_name(rop_node),
                                                                hou_farm_tools.get_simplified_rop_type_name(rop_node))

                job_id = None

                # job_index is incremented during this call by the appropriate number
                exec("job_id, job_index = "+submit_func_name+"(rop_node, job_index, dependency_list, validate_only, batch_name)")

                # Store the job_id so we can locate it again when another node is dependent on this one
                job_id_dict[rop_node.path()] = job_id

                count += 1
                operation.updateProgress(count/task_count)

# --------------------------------------------------------------------------
# Parameter Marshalling
# --------------------------------------------------------------------------


def handle_parms_job(rop_node, job_parm_dict):
    """
    Retrieves the UI Job parameters and inserts them into the job dictionary for submission

    Args:
        rop_node (hou.RopNode): The ROP node to retrieve the parameter values from
        job_parm_dict (dict): The dictionary to add the values to

    Returns:
        None
    """
    job_parm_dict["Name"] = rop_node.parm("hf_job_name").evalAsString()
    job_parm_dict["Comment"] = rop_node.parm("hf_comment").evalAsString()
    job_parm_dict["Department"] = "3D"


def handle_parms_submit(rop_node, job_parm_dict):
    """
    Retrieves the UI Submit parameters and inserts them into the job dictionary for submission

    Args:
        rop_node (hou.RopNode): The ROP node to retrieve the parameter values from
        job_parm_dict (dict): The dictionary to add the values to

    Returns:
        None
    """
    if rop_node.parm("hf_override_frames").evalAsInt() == 1:
        frame_str = rop_node.parm("hf_frames").evalAsString()
        job_parm_dict["Frames"] = frame_str
    else:
        min_frame = int(round(rop_node.parm("f1").evalAsFloat()))
        max_frame = int(round(rop_node.parm("f2").evalAsFloat()))
        step_by_frames = int(round(rop_node.parm("f3").evalAsFloat()))
        job_parm_dict["Frames"] = "{0}-{1}:{2}".format(min_frame, max_frame, step_by_frames)


def handle_parms_houdini(rop_node, job_parm_dict):
    """
    Retrieves the UI Houdini/IFD parameters and inserts them into the job dictionary for submission

    Args:
        rop_node (hou.RopNode): The ROP node to retrieve the parameter values from
        job_parm_dict (dict): The dictionary to add the values to

    Returns:
        None
    """
    job_parm_dict["Pool"] = rop_node.parm("hf_houdini_pool").evalAsString()
    job_parm_dict["SecondaryPool"] = rop_node.parm("hf_houdini_secondary_pool").evalAsString()
    job_parm_dict["Group"] = rop_node.parm("hf_houdini_group").evalAsString()
    job_parm_dict["Priority"] = rop_node.parm("hf_houdini_priority").evalAsInt()

    if rop_node.parm("hf_houdini_split_by").evalAsString() == "frames":
        job_parm_dict["ChunkSize"] = rop_node.parm("hf_houdini_frames").evalAsInt()
    else:
        int_seq = integer_sequence_from_deadline_range_spec(job_parm_dict["Frames"])
        min_frame, max_frame = int_seq.get_range()
        job_parm_dict["ChunkSize"] = 1 + int(float(max_frame - min_frame)/float(rop_node.parm("hf_houdini_chunks").evalAsInt()))


def handle_parms_houdini_advanced(rop_node, job_parm_dict):
    """
    Retrieves the UI Advanced Houdini/IFD parameters and inserts them into the job dictionary for submission

    Args:
        rop_node (hou.RopNode): The ROP node to retrieve the parameter values from
        job_parm_dict (dict): The dictionary to add the values to

    Returns:
        None
    """
    job_parm_dict["EnableAutoTimeout"] = rop_node.parm("hf_houdini_enable_auto_timeout").evalAsInt()
    job_parm_dict["TaskTimeoutMinutes"] = rop_node.parm("hf_houdini_task_timeout").evalAsInt()
    job_parm_dict["LimitConcurrentTasksToNumberOfCpus"] = rop_node.parm("hf_houdini_submit_limit_to_slave_limit").evalAsInt()
    job_parm_dict["ConcurrentTasks"] = rop_node.parm("hf_houdini_concurrent_tasks").evalAsInt()
    job_parm_dict["MachineLimit"] = rop_node.parm("hf_houdini_machine_limit").evalAsInt()
    job_parm_dict["LimitGroups"] = rop_node.parm("hf_houdini_limits").evalAsString()
    job_parm_dict["OnJobComplete"] = "Nothing"

    if rop_node.parm("hf_houdini_submit_machine_list_is_blacklist").evalAsInt() == 1:
        job_parm_dict["BlackList"] = rop_node.parm("hf_houdini_machine_list").evalAsString()
    else:
        job_parm_dict["WhiteList"] = rop_node.parm("hf_houdini_machine_list").evalAsString()


def handle_parms_mantra(rop_node, job_parm_dict):
    """
    Retrieves the UI Mantra parameters and inserts them into the job dictionary for submission

    Args:
        rop_node (hou.RopNode): The ROP node to retrieve the parameter values from
        job_parm_dict (dict): The dictionary to add the values to

    Returns:
        None
    """
    job_parm_dict["Pool"] = rop_node.parm("hf_mantra_pool").evalAsString()
    job_parm_dict["SecondaryPool"] = rop_node.parm("hf_mantra_secondary_pool").evalAsString()
    job_parm_dict["Group"] = rop_node.parm("hf_mantra_group").evalAsString()
    job_parm_dict["Priority"] = rop_node.parm("hf_mantra_priority").evalAsInt()


def handle_parms_mantra_advanced(rop_node, job_parm_dict):
    """
    Retrieves the UI Advanced Mantra parameters and inserts them into the job dictionary for submission

    Args:
        rop_node (hou.RopNode): The ROP node to retrieve the parameter values from
        job_parm_dict (dict): The dictionary to add the values to

    Returns:
        None
    """
    job_parm_dict["EnableAutoTimeout"] = rop_node.parm("hf_mantra_enable_auto_timeout").evalAsInt()
    job_parm_dict["TaskTimeoutMinutes"] = rop_node.parm("hf_mantra_task_timeout").evalAsInt()
    job_parm_dict["LimitConcurrentTasksToNumberOfCpus"] = rop_node.parm("hf_mantra_submit_limit_to_slave_limit").evalAsInt()
    job_parm_dict["ConcurrentTasks"] = rop_node.parm("hf_mantra_concurrent_tasks").evalAsInt()
    job_parm_dict["MachineLimit"] = rop_node.parm("hf_mantra_machine_limit").evalAsInt()
    job_parm_dict["LimitGroups"] = rop_node.parm("hf_mantra_limits").evalAsString()
    job_parm_dict["OnJobComplete"] = "Nothing"

    if rop_node.parm("hf_mantra_submit_machine_list_is_blacklist").evalAsInt() == 1:
        job_parm_dict["BlackList"] = rop_node.parm("hf_mantra_machine_list").evalAsString()
    else:
        job_parm_dict["WhiteList"] = rop_node.parm("hf_mantra_machine_list").evalAsString()


# --------------------------------------------------------------------------
# Node Submission
# --------------------------------------------------------------------------


def submit_geometry_type_task(rop_node, job_index, dependency_list, validate_only, output_dir_parm_name, job_name_suffix, batch_name=None):
    """
    Submits a generic task to Deadline.

    Args:
        rop_node (hou.RopNode): The Geometry ROP node to submit
        job_index (int): Unique incrementing job index
        dependency_list (list of strings): List of job identifies that this job depends on
        validate_only (bool): If set to True, it will only validate the nodes and no submission will happen.
        output_dir_parm_name (str): Name of the parameter that contains the output path
        job_name_suffix (str): String to be appended to the job name displayed in Deadline, e.g. " (ifd)"
        batch_name (str): A name to group all the similar jobs under

    Returns:
        (string, int): A tuple pair of values. The first is the job identifier, the second is the new
        value for the job index. Some nodes (IFD) submit multiple jobs, so this keeps it consistent
    """
    job_parm_dict = {}

    handle_parms_job(rop_node, job_parm_dict)
    handle_parms_submit(rop_node, job_parm_dict)
    handle_parms_houdini(rop_node, job_parm_dict)
    handle_parms_houdini_advanced(rop_node, job_parm_dict)

    job_parm_dict["Plugin"] = "Houdini"

    full_dependency_list = []
    full_dependency_list.extend(dependency_list)
    full_dependency_list.extend(rop_node.parm("hf_houdini_dependencies").evalAsString().split(","))
    dependency_str = ",".join(full_dependency_list)
    dependency_str = dependency_str.strip()
    job_parm_dict["JobDependencies"] = dependency_str

    # Customise options for the node
    job_parm_dict["OutputDirectory0"] = os.path.dirname(rop_node.parm(output_dir_parm_name).eval())
    job_parm_dict["Name"] += job_name_suffix

    if batch_name is not None:
        job_parm_dict["BatchName"] = batch_name

    plugin_parm_dict = {
        "SceneFile": hou.hipFile.path(),
        "OutputDriver": rop_node.path(),
        "IgnoreInputs": "1",
        "Version": hou_farm_tools.get_hou_major_version(),
        "Build": "64bit"}

    if validate_only:
        # Supply a dummy job id
        job_id = job_index
    else:
        # Send the job to the farm
        submit_filename, plugin_filename = write_job_files("houdini", job_index, job_parm_dict, plugin_parm_dict)
        job_id = submit_job_files_to_deadline(submit_filename, plugin_filename,
                                              rop_node.parm("hf_submit_scene").evalAsInt() == 1)

    return job_id, job_index+1


def submit_node_driver_geometry(rop_node, job_index, dependency_list, validate_only, batch_name=None):
    """
    Submits the Geometry ROP node to Deadline.

    Args:
        rop_node (hou.RopNode): The Geometry ROP node to submit
        job_index (int): Unique incrementing job index
        dependency_list (list of strings): List of job identifies that this job depends on
        validate_only (bool): If set to True, it will only validate the nodes and no submission will happen. 
        batch_name (str): A name to group all the similar jobs under

    Returns:
        (string, int): A tuple pair of values. The first is the job identifier, the second is the new
        value for the job index. Some nodes (IFD) submit multiple jobs, so this keeps it consistent
    """
    return submit_geometry_type_task(rop_node, job_index, dependency_list, validate_only, "sopoutput", "", batch_name)


def submit_node_driver_ifd(rop_node, job_index, dependency_list, validate_only, batch_name=None):
    """
    Submits the IFD (Mantra) ROP node to Deadline.

    Args:
        rop_node (hou.RopNode): The Mantra ROP node to submit
        job_index (int): Unique incrementing job index
        dependency_list (list of strings): List of job identifies that this job depends on
        validate_only (bool): If set to True, it will only validate the nodes and no submission will happen.
        batch_name (str): A name to group all the similar jobs under

    Returns:
        (string, int): A tuple pair of values. The first is the job identifier, the second is the new
        value for the job index. This node submits multiple jobs, so it needs to communicate this.
    """
    assert(rop_node.type().name() == "ifd")

    ifd_job_id, job_index = submit_geometry_type_task(rop_node, job_index, dependency_list, validate_only,
                                                      "soho_diskfile", " (ifd)", batch_name)

    job_parm_dict = {}
    handle_parms_job(rop_node, job_parm_dict)
    handle_parms_submit(rop_node, job_parm_dict)
    handle_parms_mantra(rop_node, job_parm_dict)
    handle_parms_mantra_advanced(rop_node, job_parm_dict)

    job_parm_dict["Plugin"] = "Mantra"
    job_parm_dict["Name"] += " (mantra)"
    job_parm_dict["IsFrameDependent"] = "true"

    job_parm_dict["JobDependencies"] = str(ifd_job_id)

    job_parm_dict["OutputFilename0"] = hou_farm_tools.get_expanded_render_path(rop_node, "vm_picture", "#")

    if batch_name is not None:
        job_parm_dict["BatchName"] = batch_name

    plugin_parm_dict = {
        "SceneFile": hou_farm_tools.get_expanded_render_path(rop_node, "soho_diskfile", "0"),
        "Threads": "0",
        "Version": hou_farm_tools.get_hou_major_version(),
        "CommandLineOptions": hou_farm_tools.get_mantra_commandline_options(rop_node)}

    if validate_only:
        # Supply a dummy job id
        job_id = job_index
    else:
        # Send the job to the farm
        submit_filename, plugin_filename = write_job_files("mantra", job_index, job_parm_dict, plugin_parm_dict)
        job_id = submit_job_files_to_deadline(submit_filename, plugin_filename, False)  # IFD, no need to submit scene

    return job_id, job_index+1


def submit_node_driver_alembic(rop_node, job_index, dependency_list, validate_only, batch_name=None):
    """
    Submits the Alembic ROP node to Deadline.
    Simply wraps a call to the Geometry ROP's submission. See submit_node_driver_geometry() for more information.
    """
    return submit_geometry_type_task(rop_node, job_index, dependency_list, validate_only, "sopoutput", "", batch_name)


def submit_node_driver_ifdarchive(rop_node, job_index, dependency_list, validate_only, batch_name=None):
    """
    Submits the IFD Archive ROP node to Deadline.
    Simply wraps a call to the Geometry ROP's submission. See submit_node_driver_geometry() for more information.
    """
    return submit_geometry_type_task(rop_node, job_index, dependency_list, validate_only, "sopoutput", "", batch_name)


def submit_node_driver_comp(rop_node, job_index, dependency_list, validate_only, batch_name=None):
    """
    Submits the Comp ROP node to Deadline.
    Simply wraps a call to the Geometry ROP's submission. See submit_node_driver_geometry() for more information.
    """
    return submit_geometry_type_task(rop_node, job_index, dependency_list, validate_only, "sopoutput", "", batch_name)


def submit_node_driver_channel(rop_node, job_index, dependency_list, validate_only, batch_name=None):
    """
    Submits the Channel ROP node to Deadline.
    Simply wraps a call to the Geometry ROP's submission. See submit_node_driver_geometry() for more information.
    """
    return submit_geometry_type_task(rop_node, job_index, dependency_list, validate_only, "sopoutput", "", batch_name)


def submit_node_driver_baketexture(rop_node, job_index, dependency_list, validate_only, batch_name=None):
    """
    Submits the BakeTexture ROP node to Deadline.
    Simply wraps a call to the Geometry ROP's submission. See submit_node_driver_geometry() for more information.
    """
    return submit_geometry_type_task(rop_node, job_index, dependency_list, validate_only, "sopoutput", "", batch_name)


def submit_node_driver_opengl(rop_node, job_index, dependency_list, validate_only, batch_name=None):
    """
    Submits the OpenGL ROP node to Deadline.
    Simply wraps a call to the Geometry ROP's submission. See submit_node_driver_geometry() for more information.
    """
    return submit_geometry_type_task(rop_node, job_index, dependency_list, validate_only, "picture", "", batch_name)


def submit_node_driver_dop(rop_node, job_index, dependency_list, validate_only, batch_name=None):
    """
    Submits the DOP ROP node to Deadline.
    Simply wraps a call to the Geometry ROP's submission. See submit_node_driver_geometry() for more information.
    """
    return submit_geometry_type_task(rop_node, job_index, dependency_list, validate_only, "sopoutput", "", batch_name)


def submit_node_driver_baketexture__3_0(rop_node, job_index, dependency_list, validate_only, batch_name=None):
    """
    Submits the BakeTexture ROP node to Deadline. Based on the  IFD (Mantra) ROP node code

    Args:
        rop_node (hou.RopNode): The BakeTexture ROP node to submit
        job_index (int): Unique incrementing job index
        dependency_list (list of strings): List of job identifies that this job depends on
        validate_only (bool): If set to True, it will only validate the nodes and no submission will happen.
        batch_name (str): A name to group all the similar jobs under

    Returns:
        (string, int): A tuple pair of values. The first is the job identifier, the second is the new
        value for the job index. This node submits multiple jobs, so it needs to communicate this.
    """
    assert(rop_node.type().name() == "baketexture::3.0")

    ifd_job_id, job_index = submit_geometry_type_task(rop_node, job_index, dependency_list, validate_only,
                                                      "soho_diskfile", " (ifd)", batch_name)

    job_parm_dict = {}
    handle_parms_job(rop_node, job_parm_dict)
    handle_parms_submit(rop_node, job_parm_dict)
    handle_parms_mantra(rop_node, job_parm_dict)
    handle_parms_mantra_advanced(rop_node, job_parm_dict)

    job_parm_dict["Plugin"] = "Mantra"
    job_parm_dict["Name"] += " (mantra)"
    job_parm_dict["IsFrameDependent"] = "true"

    job_parm_dict["JobDependencies"] = str(ifd_job_id)

    job_parm_dict["OutputFilename0"] = hou_farm_tools.get_expanded_render_path(rop_node, "vm_uvoutputpicture1", "#")

    if batch_name is not None:
        job_parm_dict["BatchName"] = batch_name

    plugin_parm_dict = {
        "SceneFile": hou_farm_tools.get_expanded_render_path(rop_node, "soho_diskfile", "0"),
        "Threads": "0",
        "Version": hou_farm_tools.get_hou_major_version(),
        "CommandLineOptions": hou_farm_tools.get_mantra_commandline_options(rop_node)}

    if validate_only:
        # Supply a dummy job id
        job_id = job_index
    else:
        # Send the job to the farm
        submit_filename, plugin_filename = write_job_files("mantra", job_index, job_parm_dict, plugin_parm_dict)
        job_id = submit_job_files_to_deadline(submit_filename, plugin_filename, False)  # IFD, no need to submit scene

    return job_id, job_index+1


def submit_node_sop_rop_geometry(rop_node, job_index, dependency_list, validate_only, batch_name=None):
    """
    Submits the Rop_Geometry SOP node to Deadline.
    Simply wraps a call to the Geometry ROP's submission. See submit_node_driver_geometry() for more information.
    """
    return submit_geometry_type_task(rop_node, job_index, dependency_list, validate_only, "sopoutput", "", batch_name)



# --------------------------------------------------------------------------
# Node Validation
# --------------------------------------------------------------------------


def validate_rop_list(rop_list, error_list_obj=None):
    """
    Checks a supplied list of rops to see if a) They're supported, and b) if they pass the validation checks

    Args:
        rop_list (list of hou.RopNode): A list of ROPs to check
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        Bool: True if succeeded, False if there are any problems
    """

    module_filename = __file__
    if module_filename.endswith(".pyc"):
        module_filename = module_filename[:-1]

    md5_encoder = hashlib.md5()
    md5_encoder.update(module_filename)
    this_module = imp.load_source(md5_encoder.hexdigest(), module_filename)

    module_funcs = [item for item in dir(this_module) if callable(getattr(this_module, item))]

    # Keep original pwd() to restore again at the end
    cur_pwd_node = hou.pwd()
    
    success = True

    with RopErrorList(error_list_obj) as error_list_obj:

        for rop_node in rop_list:
            hou.cd(rop_node.path())  # Make each ROP the current path for correct evaluation of relative paths during loop

            if rop_node.isBypassed():
                continue
            
            check_func_name = "validate_node_{0}_{1}".format(hou_farm_tools.get_rop_context_name(rop_node),
                                                              hou_farm_tools.get_simplified_rop_type_name(rop_node))
            has_checker = check_func_name in module_funcs

            submit_func_name = "submit_node_{0}_{1}".format(hou_farm_tools.get_rop_context_name(rop_node),
                                                              hou_farm_tools.get_simplified_rop_type_name(rop_node))
            has_submitter = submit_func_name in module_funcs

            if not has_checker and not has_submitter:
                error_list_obj.add(RopErrorMessage(rop_node, "ROP not supported"))
                success = False
            elif not has_checker:
                error_list_obj.add(RopErrorMessage(rop_node, "ROP support missing validation function: " +
                                                   check_func_name+"()"))
                success = False
            elif not has_submitter:
                error_list_obj.add(RopErrorMessage(rop_node, "ROP support missing submission function: " +
                                                   submit_func_name+"()"))
                success = False
            else:
                exec(check_func_name+"(rop_node, error_list_obj)")

        hou.cd(cur_pwd_node.path())

        return success


def validate_node_driver_geometry(rop_node, error_list_obj):
    """
    Performs some simple validation tests on a Geometry ROP to make sure no silly mistakes have been made.
    Currently checks for:

    * Valid SOP target in "soppath" parameter
    * Non empty filename in "sopoutput" parameter
    * A proper frame range is specified in "trange" (i.e. not set to "Render Current Frame"

    Args:
        rop_node (hou.RopNode): The Geometry ROP node to check
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        None
    """

    with RopErrorList(error_list_obj) as error_list_obj:

        sop_path = rop_node.parm("soppath").evalAsString()
        sop_node = hou.node(sop_path)
        if sop_node is None:
            error_list_obj.add(RopErrorMessage(rop_node, "Missing SOP Target"))

        sop_output = rop_node.parm("sopoutput").evalAsString()
        if sop_output == "":
            error_list_obj.add(RopErrorMessage(rop_node, "Missing filename"))

        frame_mode = rop_node.parm("trange").evalAsString()
        hf_override_frames = rop_node.parm("hf_override_frames").eval()
        if frame_mode == "off" and hf_override_frames == 0:
            error_list_obj.add(RopErrorMessage(rop_node, "No frame range specified"))


def validate_node_driver_ifd(rop_node, error_list_obj):
    """
    Performs some simple validation tests on a IFD (Mantra) ROP to make sure no silly mistakes have been made.
    Currently checks for:

    * Ensure the IFD Export parameter is enabled
    * Make sure the IFD path isn't just the default path: $HIP/test.ifd
    * Make sure the IFD path has a frame counter variable ($F, $F4, ${F4}, etc.) somewhere in it
    * A correct file extension for the IFD file
    * A valid value for the Houdini and Mantra Pools (i.e. not "none")
    * A valid camera pointed to by the "camera" parameter
    * Issue a warning if the camera has the background image enabled with a valid path
    * A proper frame range is specified in "trange" (i.e. not set to "Render Current Frame"

    Args:
        rop_node (hou.RopNode): The Geometry ROP node to check
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        None
    """

    with RopErrorList(error_list_obj) as error_list_obj:
        soho_outputmode = rop_node.parm("soho_outputmode").eval()
        if soho_outputmode == 0:
            error_list_obj.add(RopErrorMessage(rop_node, "IFD export not enabled"))

        regex = re.compile(r".*[\\/][^\\/]*(\$\{?F[0-9]*\}?)[^\\/]*\.([^\\/]*)$")
        soho_diskfile = rop_node.parm("soho_diskfile").unexpandedString()
        if soho_diskfile == r"$HIP/test.ifd":
            error_list_obj.add(RopWarningMessage(rop_node, "IFD path hasn't been changed from Houdini's default"))
        else:
            match_obj = regex.match(soho_diskfile)
            if match_obj is None:
                error_list_obj.add(RopWarningMessage(rop_node, "Possible misformed path for IFD. "
                                                     "Needs to be something like \"filename.$F.ifd\""))
            elif match_obj.groups()[1] != "ifd":
                error_list_obj.add(RopWarningMessage(rop_node, "Incorrect file extension for IFD file"))

        ifd_pool = rop_node.parm("hf_houdini_pool").eval()
        if ifd_pool == "" or ifd_pool == "none":
            error_list_obj.add(RopErrorMessage(rop_node, "No pool specified for IFD job"))

        mantra_pool = rop_node.parm("hf_mantra_pool").eval()
        if mantra_pool == "" or mantra_pool == "none":
            error_list_obj.add(RopErrorMessage(rop_node, "No pool specified for Mantra job"))

        camera = rop_node.parm("camera").evalAsString()
        cam_obj = hou.node(camera)
        if cam_obj is None:
            error_list_obj.add(RopErrorMessage(rop_node, "Camera object does not exist"))
        else:
            if cam_obj.parm("vm_bgenable").eval() == 1 and cam_obj.parm("vm_background").unexpandedString() != "":
                error_list_obj.add(RopWarningMessage(rop_node, "Camera background image enabled"))

        frame_mode = rop_node.parm("trange").evalAsString()
        hf_override_frames = rop_node.parm("hf_override_frames").eval()
        if frame_mode == "off" and hf_override_frames == 0:
            error_list_obj.add(RopErrorMessage(rop_node, "No frame range specified"))


def validate_node_driver_alembic(rop_node, error_list_obj):
    """
    Performs some simple validation tests on an Alembic ROP to make sure no silly mistakes have been made.
    Simply wraps a call to the Geometry ROP's validator. See validate_node_driver_geometry() for more information.
    """
    return validate_node_driver_geometry(rop_node, error_list_obj)


def validate_node_driver_ifdarchive(rop_node, error_list_obj):
    """
    Performs some simple validation tests on an IFD Archive ROP to make sure no silly mistakes have been made.
    Simply wraps a call to the Geometry ROP's validator. See validate_node_driver_geometry() for more information.
    """
    return validate_node_driver_geometry(rop_node, error_list_obj)


def validate_node_driver_comp(rop_node, error_list_obj):
    """
    Performs some simple validation tests on a Comp ROP to make sure no silly mistakes have been made.
    Simply wraps a call to the Geometry ROP's validator. See validate_node_driver_geometry() for more information.
    """
    return validate_node_driver_geometry(rop_node, error_list_obj)


def validate_node_driver_channel(rop_node, error_list_obj):
    """
    Performs some simple validation tests on a Node ROP to make sure no silly mistakes have been made.
    Simply wraps a call to the Geometry ROP's validator. See validate_node_driver_geometry() for more information.
    """
    return validate_node_driver_geometry(rop_node, error_list_obj)


def validate_node_driver_baketexture(rop_node, error_list_obj):
    """
    Performs some simple validation tests on a BakeTexture ROP to make sure no silly mistakes have been made.
    Simply wraps a call to the Geometry ROP's validator. See validate_node_driver_geometry() for more information.
    """
    return validate_node_driver_geometry(rop_node, error_list_obj)


def validate_node_driver_opengl(rop_node, error_list_obj):
    """
    Performs some simple validation tests on a OpenGL ROP to make sure no silly mistakes have been made.
    Currently checks for:

    * Non empty filename in "picture" parameter
    * A valid camera pointed to by the "camera" parameter
    * A proper frame range is specified in "trange" (i.e. not set to "Render Current Frame"

    Args:
        rop_node (hou.RopNode): The OpenGL ROP node to check
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        None
    """

    with RopErrorList(error_list_obj) as error_list_obj:

        sop_output = rop_node.parm("picture").evalAsString()
        if sop_output == "":
            error_list_obj.add(RopErrorMessage(rop_node, "Missing filename"))

        camera = rop_node.parm("camera").evalAsString()
        cam_obj = hou.node(camera)
        if cam_obj is None:
            error_list_obj.add(RopErrorMessage(rop_node, "Camera object does not exist"))
        else:
            if cam_obj.parm("vm_bgenable").eval() == 1 and cam_obj.parm("vm_background").unexpandedString() != "":
                error_list_obj.add(RopWarningMessage(rop_node, "Camera background image enabled"))

        frame_mode = rop_node.parm("trange").evalAsString()
        hf_override_frames = rop_node.parm("hf_override_frames").eval()
        if frame_mode == "off" and hf_override_frames == 0:
            error_list_obj.add(RopErrorMessage(rop_node, "No frame range specified"))


def validate_node_driver_dop(rop_node, error_list_obj):
    """
    Performs some simple validation tests on a DOP ROP to make sure no silly mistakes have been made.
    Simply wraps a call to the Geometry ROP's validator. See validate_node_driver_geometry() for more information.
    """
    return validate_node_driver_geometry(rop_node, error_list_obj)


def validate_node_driver_baketexture__3_0(rop_node, error_list_obj):
    """
    Performs some simple validation tests on a BakeTexture ROP to make sure no silly mistakes have been made.
    Simply wraps a call to the Geometry ROP's validator. See validate_node_driver_ifd() for more information.
    """
    return validate_node_driver_ifd(rop_node, error_list_obj)


def validate_node_sop_rop_geometry(rop_node, error_list_obj):
    """
    Performs some simple validation tests on a Rop_Geometry SOP to make sure no silly mistakes have been made.
    Simply wraps a call to the Geometry ROP's validator. See validate_node_driver_geometry() for more information.
    """
    return validate_node_driver_geometry(rop_node, error_list_obj)
