from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Plugin(Strict):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal['eq', 'compressor', 'limiter', 'reverb', 'delay', 'saturation', 'other'] = 'other'
    bypass: bool = False


class Channel(Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,40}$')
    name: str = Field(min_length=1, max_length=80)
    kind: Literal['vocal', 'backing', 'adlib', 'beat', 'bus', 'return', 'master', 'other']
    fader_db: float = Field(default=0, ge=-60, le=12)
    pan: float = Field(default=0, ge=-1, le=1)
    width: float = Field(default=1, ge=0, le=2)
    plugins: list[Plugin] = Field(default_factory=list, max_length=30)


class Route(Strict):
    source: str
    target: str
    kind: Literal['output', 'send'] = 'output'
    gain_db: float = Field(default=0, ge=-60, le=12)


class Session(Strict):
    daw: str = Field(min_length=1, max_length=80)
    bpm: float = Field(ge=30, le=300)
    stage: Literal['mix', 'master']
    beat_source: Literal['stereo', 'multitrack']
    beat_already_limited: Literal['yes', 'no', 'unknown']
    export_sample_rate: int = Field(ge=8000, le=96000)
    export_bit_depth: Literal['16', '24', '32-float']
    listening_setup: str = Field(min_length=1, max_length=300)
    intent: str = Field(min_length=1, max_length=1000)
    channels: list[Channel] = Field(min_length=2, max_length=64)
    routes: list[Route] = Field(max_length=128)

    @model_validator(mode='after')
    def graph(self):
        ids = [c.id for c in self.channels]
        masters = [c.id for c in self.channels if c.kind == 'master']
        if len(set(ids)) != len(ids) or len(masters) != 1:
            raise ValueError('Use IDs únicos e exatamente um master.')
        master = masters[0]
        edges = {i: [] for i in ids}
        outputs = set()
        pairs = set()
        for r in self.routes:
            if r.source not in edges or r.target not in edges or r.source == master:
                raise ValueError('Rota inválida ou saída do master.')
            if (r.source, r.target) in pairs:
                raise ValueError('Rota duplicada.')
            pairs.add((r.source, r.target))
            if r.kind == 'output':
                if r.source in outputs:
                    raise ValueError('Cada canal aceita apenas uma saída principal.')
                outputs.add(r.source)
            edges[r.source].append(r.target)
        visiting, done = set(), set()

        def visit(node):
            if node in visiting:
                raise ValueError('Feedback/ciclo de roteamento não permitido.')
            if node in done:
                return
            visiting.add(node)
            for target in edges[node]:
                visit(target)
            visiting.remove(node)
            done.add(node)
        for node in ids:
            visit(node)
            if node != master and node not in outputs:
                raise ValueError('Todo canal precisa de uma saída principal até o master.')
        return self


class TrackCreate(Strict):
    title: str = Field(min_length=1, max_length=120)
    session: Session


class Answer(Strict):
    question_id: str = Field(min_length=1, max_length=180)
    answer: str = Field(min_length=1, max_length=2000)
