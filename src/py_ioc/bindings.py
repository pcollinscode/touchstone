import abc
import builtins
import inspect
import typing
from typing import (
    Any,
    Callable,
    Dict,
    Hashable,
    Optional,
)

from py_ioc.exceptions import BindingError

SINGLETON = 'singleton'
NEW_EVERY_TIME = 'new_every_time'

TAbstract = Hashable
TConcrete = Callable

BUILTIN_TYPES = {getattr(builtins, t) for t in dir(builtins) if isinstance(getattr(builtins, t), type)}
TYPING_TYPES = {getattr(typing, t) for t in dir(typing) if isinstance(getattr(typing, t), type)}


def is_builtin(abstract: TAbstract):
    return abstract in BUILTIN_TYPES


def is_typing(abstract: TAbstract):
    return abstract in TYPING_TYPES or type(abstract) in TYPING_TYPES


class AbstractBinding(abc.ABC):
    abstract: Optional[TAbstract]
    concrete: TConcrete
    lifetime_strategy: str

    @abc.abstractmethod
    def is_contextual(self) -> bool:
        pass

    @abc.abstractmethod
    def __hash__(self):
        pass

    def make(self, fulfilled_params: Dict[str, Any]) -> Any:
        return self.concrete(**fulfilled_params)

    def get_concrete_params(self) -> Dict[str, Any]:
        """
        Returns a dict for the concrete parameters, a dictionary carrying the kwarg-name to its annotation.
        """
        sig = inspect.signature(self.concrete)
        return {
            name: param.annotation
            for name, param in sig.parameters.items()
            if param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        }

    def get_concrete_attrs(self) -> Dict[str, Any]:
        """
        Returns a dict for the concrete's attribute annotations, that is `self.concrete.__annotations__`.
        Excludes ClassVar typehints and excludes annotations that exist as attributes on the concrete class itself.
        """
        try:
            return {
                param: annotation
                for param, annotation in self.concrete.__annotations__.items()
                if not hasattr(self.concrete, param) and not isinstance(annotation, type(typing.ClassVar))
            }
        except AttributeError:
            return {}


class SimpleBinding(AbstractBinding):
    def __init__(self, abstract: TAbstract, concrete: TConcrete, lifetime_strategy: str) -> None:
        if is_builtin(abstract):
            raise BindingError("Cannot bind builtin type {}".format(abstract))
        self.abstract = abstract
        self.concrete = concrete  # type: ignore
        self.lifetime_strategy = lifetime_strategy

    def is_contextual(self) -> bool:
        return False

    def __hash__(self) -> int:
        return hash((self.abstract, self.concrete, self.lifetime_strategy))


class AutoBinding(AbstractBinding):
    lifetime_strategy = NEW_EVERY_TIME

    def __init__(self, abstract) -> None:
        if (not callable(abstract)
                or inspect.isabstract(abstract)
                or abstract is inspect.Parameter.empty
                or is_builtin(abstract)
                or is_typing(abstract)):
            raise BindingError("Cannot create auto-binding for typing type {}".format(abstract))
        self.abstract = abstract
        self.concrete = abstract  # type: ignore

    def is_contextual(self) -> bool:
        return False

    def __hash__(self) -> int:
        return hash((self.abstract, self.concrete))


class ContextualBinding(AbstractBinding):
    def __init__(self, abstract: Optional[TAbstract], concrete: TConcrete, lifetime_strategy: str,
                 parent: TConcrete, parent_name: Optional[str]) -> None:
        if abstract is None and parent_name is None:
            raise BindingError("Cannot create contextual binding with no context.")
        self.abstract = abstract
        self.concrete = concrete  # type: ignore
        self.lifetime_strategy = lifetime_strategy
        self.parent = parent
        self.parent_name = parent_name

    def is_contextual(self) -> bool:
        return True

    def __hash__(self) -> int:
        hash_data = (self.abstract, self.concrete, self.lifetime_strategy, self.parent, self.parent_name)
        return hash(hash_data)


TBinding = typing.Union[AutoBinding, SimpleBinding, ContextualBinding]
