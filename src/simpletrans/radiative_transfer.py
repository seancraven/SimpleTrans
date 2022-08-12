"""
The Simple Trans Project development and mathematical models are documented
in detail by The CDS_book.

The AtmosphereGrid must be connected to the database made in
__main__.py, which is set by the user, when it is first run.

This file provides the main class AtmosphereGrid, from which radiative
transfer is implemented for Earth's atmosphere. The Atmosphere grid
describes a 1d atmosphere in space, with wavenumber as the second
dimension.

This enables simplistic modeling of radiative transfer, which is dependent
on the molecules in the air.

alt is short for altitude
wave_no is short for wavenumber

"""
import os.path
import sqlite3
from typing import Tuple
from simpletrans import isa
import numpy as np
import pandas as pd
from numpy.typing import ArrayLike
from simpletrans.plank import plank_nu
from tqdm import tqdm
from simpletrans.database_interacton import default_db

# %



def fetch_od_from_db(
    connection: sqlite3.Connection,
    gas: str,
    alt_range: Tuple[float, float],
    wave_no_range: Tuple[float, float],
    verbose: bool,
) -> Tuple[dict[int:ArrayLike], ArrayLike]:
    """
    Returns a smoothed dict of optical depths, where the key is the
    altitude. From the optical depths database, which values are
    calculated by the __main__.py file. Additionally returns the wavenumbers
    associated with such optical depth OD(wavenumber_i).

    Only returns values in the intervals:
    [wave_no_min, wave_no_max], [alt_min, alt_max].
    Additionally, returns the bins in which the values are put into. The
    steps are also fixed, with 1cm^{-1} for wavenumber


    Args:
        verbose: Controls weather the function prints status updates.
        alt_range: A tuple of values for the range of alts
        wave_no_range: A tuple of values for the range of wave_nos
        gas: gas name, must be in database which was created.
        connection: Database Connection, with optical depths.

    Returns:
        optical_depths dictionary, binned wavenumbers.

    """
    wave_no_min, wave_no_max = wave_no_range
    alt_min, alt_max = alt_range

    sql_gas_query = (
        f"SELECT mol_id, mol_name FROM gases WHERE mol_name = '{gas}';"
    )
    gas_df = pd.read_sql_query(sql_gas_query, connection)
    gas_id = gas_df["mol_id"][0]

    sql_query = f"""
    SELECT altitude, wave_no, optical_depth FROM optical_depths
    WHERE (wave_no BETWEEN {wave_no_min} and {wave_no_max}) and
    (altitude BETWEEN {alt_min} and {alt_max}) and
    (mol_id = {gas_id});
    """
    od_array = pd.read_sql_query(sql_query, connection).to_numpy()

    sql_alt_query = "SELECT DISTINCT altitude from optical_depths"
    alts = pd.read_sql_query(sql_alt_query, connection)
    alt_list = []
    for i in alts["altitude"]:
        if (i > alt_min) and (i < alt_max):
            alt_list.append(i)
    od_dict = {}
    if verbose:
        disable_tdqm = False
    else:
        disable_tdqm = True
    for alt in tqdm(alt_list, disable=disable_tdqm):
        mask = od_array[:, 0] == alt
        ods = od_array[mask]
        binned_wave_nos, mean_ods = integer_bin_means(ods[:, 1], ods[:, 2])
        binned_wave_nos, mean_ods = coerce_sorted_key_value_pair_to_target(
            binned_wave_nos,
            mean_ods,
            np.arange(wave_no_min, wave_no_max + 1, dtype=int),
        )
        od_dict.update({int(alt): mean_ods})
    return od_dict, binned_wave_nos


def coerce_sorted_key_value_pair_to_target(
    a_1: ArrayLike, a_2: ArrayLike, target_array: ArrayLike
):
    """
    If two arrays represent a key value pair, with a_1 the sorted keys and
    a_2 the values.
    This function outputs an array pair with keys = target array.
    If no value for a key in target_array then it is populated with zeros.
    If a_1 has keys that are not included in target_array then the key value
    pair is dropped.
    Example:
         a_1: [0, 1, 3, 4, 6], a_2: [-1, 10, 30, 40, 60]
         a_1_target: [1, 2, 3, 4, 5 ,6]
         returns [1, 2, 3, 4, 5, 6] , [10, 0 , 30, 40, 0, 60]

    Args:
        a_1: Array of keys
        a_2: Array of Values
        target_array: Target keys to be coerced into.

    Returns:
        (target_array, padded_values)

    """
    assert a_1.shape == a_2.shape
    a_12_array = np.vstack((a_1, a_2))
    target_is_superset = set(target_array) - set(a_1)
    target_is_subset = set(a_1) - set(target_array)
    if target_is_superset:
        for entry in list(target_is_superset):
            a_12_array = np.hstack((a_12_array, np.array([[entry], [0]])))
        a_12_array = a_12_array[:, np.argsort(a_12_array[0])]
    else:
        for surplus_entry in target_is_subset:
            index = np.argwhere(a_1 == surplus_entry)
            a_12_array = np.delete(a_12_array, index, axis=1)
    return a_12_array[0], a_12_array[1]


def integer_bin_means(
    column_0: ArrayLike, column_1: ArrayLike
) -> Tuple[ArrayLike, ArrayLike]:
    """
    Assumes that column_0 is key in that the values in colum_1[i]
    are associated with float key column_0[i].
    The float keys are rounded to the nearest integer, all values
    with the same integer key are averaged over.
    Example:
        column_1: [0.1,0.5,1.2] column_2: [1,3,5]
        returns [0,1] [1,4]
    Args:
        column_0: Float Key to be binned.
        column_1: Values to be averaged over.

    Returns:
        integer_keys, bin_mean_values

    """
    assert column_0.shape == column_1.shape
    int_bins = np.rint(column_0)
    col_0_unique = np.unique(int_bins)
    means = np.zeros_like(col_0_unique)
    for i, value in np.ndenumerate(col_0_unique):
        mask = int_bins == value
        means[i] = np.mean((column_1)[mask])
    return col_0_unique, means


class AtmosphereGrid:
    def __init__(
        self,
        alt_range: Tuple[float, float],
        wave_no_range: Tuple[float, float],
        *gas: str,
        verbose=False,
        db_connection: sqlite3.Connection = default_db(),
    ):
        self.alt_min, self.alt_max = alt_range
        self.wave_no_min, self.wave_no_max = wave_no_range
        self.connection = db_connection
        self.gases = gas
        self.verbose = verbose
        self.od_df, self.wave_no_bins = self.get_optical_depth()
        self.alt_list = self.od_df.columns.to_list()
        self.ones_grid = np.ones(
            (len(self.alt_list), len(self.wave_no_bins))
        )

    def get_optical_depth(self) -> tuple[ArrayLike, ArrayLike]:
        """
        calculates OD(wavenumber)
        Function to add multiple optical depths together, when more than one gas is
        passed to AtmospherGrid. Additionally returns the optical depth values for each integer wavenumber.
        Returns:
            total optical depth, wave number bins associated with the optical depth values.

        """
        od_df = 0
        for _gas in self.gases:
            if self.verbose:
                tqdm.write(f"Loading {_gas} from Database")
            else:
                pass
            od_dict, wave_no_bins = fetch_od_from_db(
                self.connection,
                _gas,
                (self.alt_min, self.alt_max),
                (self.wave_no_min, self.wave_no_max),
                verbose=self.verbose,
            )
            od_df += pd.DataFrame(od_dict)
        return od_df, wave_no_bins

    def get_blackbody_grid(self) -> ArrayLike:
        """
        When the atmosphere is treated as blocks, with an associated temperature,
        such blocks emit thermal blackbody radiation. This function calculates
        these black body values for the altitudes and wavenumbers in
        AtmosphereGrid.

        Returns:


        """
        temp_list = isa.get_temperature([int(i) for i in self.alt_list])
        temp_grid = (self.ones_grid.transpose() * temp_list).transpose()
        wave_no_grid = self.ones_grid * self.wave_no_bins.transpose()
        return plank_nu(wave_no_grid, temp_grid, flux=True).transpose()

    def flux_up(self) -> pd.DataFrame:
        """
        Calculates the total flux from the blackbody emission from both,
        earth and its warm atmosphere with the transmission profiles of the
        atmosphere due to the GHGs modelled.
        Returns:

        """
        ground_flux = plank_nu(
            self.wave_no_bins, isa.get_temperature(self.alt_min), flux=True
        )
        transmission_all_alt = np.exp(-self.od_df)
        blackbody_grid = self.get_blackbody_grid()
        # Initialise the transmission functions
        flux_from_surf = pd.DataFrame(
            (transmission_all_alt.transpose() * ground_flux).transpose()
        )
        flux_from_ith_block = transmission_all_alt * blackbody_grid
        # wavenumber grid has spacing 1 cm^(-1) such that no
        # multiplication is needed
        for i, _ in enumerate(flux_from_ith_block.iloc[0, :]):
            if i != 0:
                flux_from_ith_block.iloc[:, i] += flux_from_ith_block.iloc[
                    :, i - 1
                ]
                flux_from_surf.iloc[:, i - 1] *= flux_from_surf.iloc[
                    :, i - 1
                ]
        total_flux = flux_from_surf + flux_from_ith_block
        return pd.DataFrame(total_flux, columns=self.od_df.columns)
