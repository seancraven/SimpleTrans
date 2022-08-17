import os
import sys
from simpletrans import isa
from simpletrans.optical_depth_functions import optical_depth
from numpy.typing import ArrayLike


class HiddenPrints:
    """Suppresses prints to console"""

    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout


with HiddenPrints():
    import hapi


class Ghg:
    """
    Records ghg abundance in ppb ghg abundance assumed constant. Up to
    implemented ceiling of 10 km.

    This is the same assumption as taken by MODTRAN, which achieves
    accuracies
    better than 1k accuracy on thermal brightness temperature.
    """

    ppm = {"CO2": 411, "CH4": 1.893, "N2O": .327, "H2O": 25 * 10**9}
    ids = {"CO2": 2, "CH4": 6, "N2O": 4, "H2O": 1}


def ghg_lbl_download(path: str):
    """
    Downloads and Stores Line by line Data for 4 most abundant ghg.
    If further gases are required add a name and HITRAN id to
    molecule_id_dict. Data is collected from HITRAN.

    Assumes only most abundant isotopologue is required.

    This additionally creates a local database. This database is queried
    from in the ghg_od_calculate().
    """
    with HiddenPrints():
        hapi.db_begin(os.path.join(path, "spectral_line.db"))
        isotopologue = 1  # only want main isotopologue
        min_wavenumber = 0
        max_wavenumber = 4000  # spectral flux density
        # in (watts m^(-2)m^-1) is negligible beyond this region
        for gas, _id in Ghg.ids.items():
            hapi.fetch(
                gas, _id, isotopologue, min_wavenumber, max_wavenumber
            )


def ghg_od_calculate(
    gas: str, alt: float, ghg_ppm=None
) -> tuple[ArrayLike, ArrayLike, ArrayLike]:
    """
    Calculates the optical density of a km of atmosphere, due to a
    single gas.

    Args:
        ghg_ppm: If the gas was not in the origional databse CO2, N2O,
        H2O, CH4, this is required to calculate od.
        gas (str): string of gas name, valid gasses found in Ghg.
        alt (float): midpoint altitude of km block of atmosphere.

    Returns: (np.array, np.array): wavenumber,  optical density and
     absorbtion coef arrays of same shape.
    """
    if not ghg_ppm:
        ghg_ppm = Ghg.ppm[gas]
    temp = isa.get_temperature(alt)
    pressure = isa.get_pressure(alt)
    press_0 = isa.get_pressure(0)
    with HiddenPrints():
        nu, coef = hapi.absorptionCoefficient_Voigt(
            SourceTables=gas,
            Environment={"T": temp, "p": pressure / press_0},
            Diluent={"air": 1.0},
        )

        od = optical_depth(alt - 500, alt + 500, ghg_ppm, coef)
    return nu, od, coef
