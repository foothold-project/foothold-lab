"""W33b Kit cache argument for the next basic-gait learning and evaluation runs."""

KIT_CACHE_VALUE = "--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache"
KIT_CACHE_ARG = "--kit_args=" + KIT_CACHE_VALUE


def kit_cache_arg(environ=None) -> str:
    """The Kit cache argument for this machine.

    Without FOOTHOLD_MACHINE_PROFILE the Windows constant above is returned unchanged. With a profile
    selected (Linux, ai-lx01) the cache directory comes from the profile's isaac_cache_root.
    """
    import os
    env = os.environ if environ is None else environ
    if not env.get("FOOTHOLD_MACHINE_PROFILE"):
        return KIT_CACHE_ARG
    from foothold_s2.machine_profile import load_machine_profile
    cache = load_machine_profile(environ=env)["paths"].get("isaac_cache_root")
    if not cache:
        raise ValueError("machine profile defines no isaac_cache_root for the Kit cache argument")
    return "--kit_args=--/UJITSO/datastore/localCachePath=" + str(cache).replace("\\", "/")
