from .unit_handling import Quantity, ureg, convert_units, dimensionless_magnitude
from .adas_interface.determine_adas_dataset_type import determine_reader_class_and_config
from .shared import data_file_directory, get_git_revision_short_hash
import xarray as xr
import numpy as np

def build_raw_dataset(species_name, config):
    """Builds a rate_dataset combining all of the raw data available for a given species."""
    species_config = config["species"][species_name]
    data_file_config = config["data_file_config"]

    dataset = xr.Dataset().assign_attrs(
        atomic_number=species_config["atomic_number"],
        species_name=species_name,
        git_hash=get_git_revision_short_hash(),
    )

    dataset = write_global_attributes(dataset, config["globals"])

    for dataset_type in species_config["data_files"].keys():
        reader_key, dataset_config = determine_reader_class_and_config(
            data_file_config, dataset_type
        )
        
        match reader_key:

            case "adf11":
                rate_dataset = build_adf11_rate_dataset(data_file_directory, species_name, dataset_type, dataset_config)
            case _:
                raise NotImplementedError(f"No implementation for reading {reader_key} files.")

        determine_coordinates(dataset, rate_dataset)
        dataset[dataset_type] = rate_dataset.rate_coefficient

    dataset = dataset.pad(
        pad_width=dict(dim_charge_state=(0, 1)), mode="constant", constant_values=0.0
    )
    dataset = dataset.assign_coords(
        dim_charge_state=np.arange(dataset.sizes["dim_charge_state"])
    )

    for key in [
        "effective_recombination_coeff",
        "charge_exchange_cross_coupling_coeff",
        "recombination_and_bremsstrahlung",
        "charge_exchange_emission",
    ]:
        dataset[key] = dataset[key].roll(dim_charge_state=+1)

    return dataset

def write_global_attributes(dataset: xr.Dataset, globals: dict) -> xr.Dataset:
    
    for attribute, value in globals.items():

        if isinstance(value, dict):
            dataset[attribute] = xr.DataArray(
                Quantity(value["value"], value["units"]),
                coords={f"dim_{attribute}": value["value"]},
            )
        else:
            dataset[attribute] = value
    
    return dataset

def determine_coordinates(dataset: xr.Dataset, rate_dataset: xr.Dataset):
    
    for key in [
        "electron_density",
        "electron_temp",
        "reference_electron_density",
        "reference_electron_temp"
    ]:
        if key not in dataset:
            dataset[key] = rate_dataset[key]
    
    for key in [
        "electron_density",
        "electron_temp"
    ]:
        np.testing.assert_allclose(
            dimensionless_magnitude(
                (dataset[key] - rate_dataset[key]) / dataset[f"reference_{key}"]
            ),
            0.0
        )

def read_data_from_adf11_file(*args, **kwargs):
    from .readers import read_adf11_file
    return read_adf11_file(*args, **kwargs)

def build_adf11_rate_dataset(data_file_directory, species_name, dataset_type, dataset_config):
    data = read_data_from_adf11_file(data_file_directory, species_name, dataset_type, dataset_config)

    ds = xr.Dataset()

    ds["species"] = species_name
    ds["dataset"] = dataset_type
    ds["charge"] = data["iz0"]

    electron_density = convert_units(
        Quantity(10 ** data["ddens"][:data["idmax"]], ureg.cm**-3), ureg.m**-3
    )
    electron_temp = Quantity(10 ** data["dtev"][:data["itmax"]], ureg.eV)

    # Use logarithmic quantities to define the coordinates, so that we can interpolate over logarithmic quantities.
    ds["electron_density"] = xr.DataArray(
        electron_density, coords=dict(dim_electron_density=electron_density.magnitude)
    )
    ds["electron_temp"] = xr.DataArray(
        electron_temp, coords=dict(dim_electron_temp=electron_temp.magnitude)
    )

    ds["reference_electron_density"] = Quantity(1.0, ureg.m**-3)
    ds["reference_electron_temp"] = Quantity(1.0, ureg.eV)

    ds["number_of_charge_states"] = data["ismax"]
    charge_state = np.arange(data["ismax"])
    ds["charge_state"] = xr.DataArray(
        charge_state, coords=dict(dim_charge_state=charge_state)
    )

    coefficient = data["drcof"][:data["ismax"], :data["itmax"], :data["idmax"]]
    if dataset_config["code"] <= 9:
        coefficient = 10**coefficient

    input_units = dataset_config["stored_units"]
    output_units = dataset_config["desired_units"]
    ds["rate_coefficient"] = convert_units(
        xr.DataArray(
            coefficient,
            dims=("dim_charge_state", "dim_electron_temp", "dim_electron_density"),
        ).pint.quantify(input_units),
        output_units,
    )

    return ds