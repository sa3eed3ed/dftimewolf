# -*- coding: utf-8 -*-
"""Processes a directory of artifacts with Turbinia."""

import os
import tempfile

from typing import Optional, TYPE_CHECKING, Type

from turbinia import TurbiniaException, evidence
from turbinia import config as turbinia_config

from dftimewolf.lib import module
from dftimewolf.lib.containers import containers, interface
from dftimewolf.lib.modules import manager as modules_manager
from dftimewolf.lib.processors.turbinia_base import TurbiniaProcessorBase

if TYPE_CHECKING:
  from dftimewolf.lib import state

# pylint: disable=no-member

class TurbiniaArtifactProcessor(TurbiniaProcessorBase,
                                module.ThreadAwareModule):
  """Processes Exported GRR Artifacts with Turbinia.

  Attributes:
    directory_path (str): Name of the directory to process.
  """

  def __init__(self,
               state: "state.DFTimewolfState",
               name: Optional[str]=None,
               critical: bool=False) -> None:
    """Initializes a Turbinia Artifacts disks processor.

    Args:
      state (DFTimewolfState): recipe state.
      name (Optional[str]): The module's runtime name.
      critical (Optional[bool]): True if the module is critical, which causes
          the entire recipe to fail if the module encounters an error.
    """
    module.ThreadAwareModule.__init__(self, state, name=name, critical=critical)
    TurbiniaProcessorBase.__init__(self, self.logger)
    self.output_directory = ''

  # pylint: disable=arguments-differ
  def SetUp(self,
            turbinia_config_file: Optional[str],
            project: str,
            turbinia_recipe: Optional[str],
            turbinia_zone: str,
            output_directory: str,
            sketch_id: int) -> None:
    """Sets up the object attributes.

    Args:
      turbinia_config_file (str): Full path to the Turbinia config file to use.
      project (str): name of the GCP project containing the disk to process.
      turbinia_recipe (str): Turbinia recipe name.
      turbinia_zone (str): GCP zone in which the Turbinia server is running.
      output_directory (str): Name of the directory to process.
      sketch_id (int): The Timesketch sketch ID.
    """
    self.turbinia_config_file = turbinia_config_file
    self.output_directory = output_directory
    if not self.output_directory:
      self.output_directory = tempfile.mkdtemp(prefix='turbinia-results')
      self.PublishMessage(
          f'Turbinia results will be dumped to {self.output_directory}')
    try:
      self.TurbiniaSetUp(project, turbinia_recipe, turbinia_zone, sketch_id)
    except TurbiniaException as exception:
      self.ModuleError(str(exception), critical=True)
      return

  def Process(self, container: containers.RemoteFSPath) -> None:
    """Process files with Turbinia."""

    log_file_path = os.path.join(self._output_path,
        '{0:s}_{1:s}-turbinia.log'.format(
            container.hostname, container.path.replace('/', '_')))
    self.logger.info('Turbinia log file: {0:s}'.format(log_file_path))
    self.logger.info(
        'Processing remote FS path {0:s} from previous collector'.format(
            container.path))
    evidence_ = evidence.CompressedDirectory(
        compressed_directory=container.path, source_path=container.path)
    try:
      task_data, _ = self.TurbiniaProcess(evidence_)
    except TurbiniaException as exception:
      self.ModuleError(str(exception), critical=True)

    self.logger.info('Files generated by Turbinia:')
    for task in task_data:
      for path in task.get('saved_paths') or []:
        # Ignore temporary files generated by turbinia
        if path.startswith(turbinia_config.TMP_DIR):
          continue

        # We're only interested in plaso files for the time being.
        if path.endswith('.plaso'):
          self.PublishMessage(f'  {task["name"]}: {path}')
          container = containers.RemoteFSPath(
              path=path, hostname=container.hostname)
          self.state.StoreContainer(container)

  @staticmethod
  def GetThreadOnContainerType() -> Type[interface.AttributeContainer]:
    return containers.RemoteFSPath

  def GetThreadPoolSize(self) -> int:
    return self.parallel_count

  @staticmethod
  def KeepThreadedContainersInState() -> bool:
    return False

  def PreProcess(self) -> None:
    pass

  def PostProcess(self) -> None:
    pass

modules_manager.ModulesManager.RegisterModule(TurbiniaArtifactProcessor)
