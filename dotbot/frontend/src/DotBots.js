import React from "react";
import { useCallback, useEffect, useState } from "react";

import { useKeyPress } from "./hooks/keyPress";
import { DotBotItem } from "./DotBotItem";
import { DotBotsMap } from "./DotBotsMap";
import { SailBotItem } from "./SailBotItem";
import { SailBotsMap } from "./SailBotsMap";
import { XGOItem } from "./XGOItem";
import { ApplicationType, inactiveAddress, maxWaypoints, maxPositionHistory } from "./utils/constants";
import { computeOrcaVelocityForAgent } from "./utils/orca.tsx";
import { mul } from "./utils/vec2.tsx";


const DotBots = ({ dotbots, updateDotbots, publishCommand, publish }) => {
  const [ activeDotbot, setActiveDotbot ] = useState(inactiveAddress);
  const [ showDotBotHistory, setShowDotBotHistory ] = useState(true);
  const [ dotbotHistorySize, setDotbotHistorySize ] = useState(maxPositionHistory);
  const [ showSailBotHistory, setShowSailBotHistory ] = useState(true);

  const control = useKeyPress("Control");
  const enter = useKeyPress("Enter")
  const backspace = useKeyPress("Backspace");

  const updateActive = useCallback(async (address) => {
    setActiveDotbot(address);
  }, [setActiveDotbot]
  );

  const updateShowHistory = (show, application) => {
    if (application === ApplicationType.SailBot) {
      setShowSailBotHistory(show);
    } else {
      setShowDotBotHistory(show);
    }
  };

  const insertWaypoint = useCallback((x, y, dotbot) => {
    // Limit number of waypoints to maxWaypoints
    if (dotbot.waypoints.length >= maxWaypoints) {
      return;
    }

    if (dotbot.application === ApplicationType.SailBot) {
      let dotbotsTmp = dotbots.slice();
      for (let idx = 0; idx < dotbots.length; idx++) {
        if (dotbots[idx].address === dotbot.address) {
          if (dotbotsTmp[idx].waypoints.length === 0) {
            dotbotsTmp[idx].waypoints.push({
              latitude: dotbotsTmp[idx].gps_position.latitude,
              longitude: dotbotsTmp[idx].gps_position.longitude,
            });
          }
          dotbotsTmp[idx].waypoints.push({latitude: x, longitude: y});
          updateDotbots(dotbotsTmp);
        }
      }
    }
    if (dotbot.application === ApplicationType.DotBot) {
      let dotbotsTmp = dotbots.slice();
      for (let idx = 0; idx < dotbots.length; idx++) {
        if (dotbots[idx].address === dotbot.address) {
          if (dotbotsTmp[idx].waypoints.length === 0) {
            dotbotsTmp[idx].waypoints.push({
              x: dotbotsTmp[idx].lh2_position.x,
              y: dotbotsTmp[idx].lh2_position.y,
              z: 0
            });
          }
          dotbotsTmp[idx].waypoints.push({x: x, y: y, z: 0});
          updateDotbots(dotbotsTmp);
        }
      }
    }
  }, [dotbots, updateDotbots]
  );


  const mapClicked = useCallback((x, y) => {
    if (!dotbots || dotbots.length === 0) {
      return;
    }

    const activeDotbots = dotbots.filter(dotbot => activeDotbot === dotbot.address);
    // Do nothing if no active dotbot
    if (activeDotbots.length === 0) {
      return;
    }

    const dotbot = activeDotbots[0];
    insertWaypoint(x, y, dotbot);
  }, [activeDotbot, dotbots, insertWaypoint]
  );

  const applyWaypoints = useCallback(async (address, application) => {
    for (let idx = 0; idx < dotbots.length; idx++) {
      if (dotbots[idx].address === address) {
        await publishCommand(address, application, "waypoints", { threshold: dotbots[idx].waypoints_threshold, waypoints: dotbots[idx].waypoints });
        return;
      }
    }
  }, [dotbots, publishCommand]
  );

  const clearWaypoints = useCallback(async (address, application) => {
    let dotbotsTmp = dotbots.slice();
    for (let idx = 0; idx < dotbots.length; idx++) {
      if (dotbots[idx].address === address) {
        dotbotsTmp[idx].waypoints = [];
        await publishCommand(address, application, "waypoints", { threshold: dotbots[idx].waypoints_threshold, waypoints: [] });
        updateDotbots(dotbotsTmp);
        return;
      }
    }
  }, [dotbots, updateDotbots, publishCommand]
  );

  const clearPositionsHistory = async (address) => {
    let dotbotsTmp = dotbots.slice();
    for (let idx = 0; idx < dotbots.length; idx++) {
      if (dotbots[idx].address === address) {
        dotbotsTmp[idx].position_history = [];
        await publishCommand(address, dotbots[idx].application, "clear_position_history", "");
        updateDotbots(dotbotsTmp);
        return;
      }
    }
  };

  const updateWaypointThreshold = (address, threshold) => {
    let dotbotsTmp = dotbots.slice();
    for (let idx = 0; idx < dotbots.length; idx++) {
      if (dotbots[idx].address === address) {
        dotbotsTmp[idx].waypoints_threshold = threshold;
        updateDotbots(dotbotsTmp);
        return;
      }
    }
  };

  useEffect(() => {

    if (dotbots && control && enter) {
      if (activeDotbot !== inactiveAddress) {
        for (let idx = 0; idx < dotbots.length; idx++) {
          if (dotbots[idx].address === activeDotbot) {
            applyWaypoints(activeDotbot, dotbots[idx].application);
            break;
          }
        }
      }
    }
    if (dotbots && control && backspace) {
      if (activeDotbot !== inactiveAddress) {
        for (let idx = 0; idx < dotbots.length; idx++) {
          if (dotbots[idx].address === activeDotbot) {
            clearWaypoints(activeDotbot, dotbots[idx].application);
            break;
          }
        }
      }
    }
  }, [
    dotbots,
    control, enter, backspace,
    applyWaypoints, clearWaypoints, activeDotbot
  ]);

  let needDotBotMap = dotbots.filter(dotbot => dotbot.application === ApplicationType.DotBot).some((dotbot) => dotbot.calibrated);

  return (
    <>
    <nav className="navbar navbar-dark navbar-expand-lg bg-dark">
      <div className="container-fluid">
        <a className="navbar-brand text-light" href="http://www.dotbots.org">The DotBots project</a>
        <button className="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
          <span className="navbar-toggler-icon"></span>
        </button>
        {/* <div className="collapse navbar-collapse" id="navbarNav">
          <ul className="navbar-nav">
            <li className="nav-item">
              <a className="nav-link active" aria-current="page" href="http://localhost:8000/api" target="_blank" rel="noreferrer noopener">API</a>
            </li>
          </ul>
        </div> */}
      </div>
    </nav>
    <div className="container">
      {dotbots && dotbots.length > 0 && (
      <>
      {dotbots.filter(dotbot => dotbot.application === ApplicationType.DotBot).length > 0 &&
      <div className="row">
        <div className={`col ${needDotBotMap ? "col-xxl-6" : ""}`}>
          <div className="card m-1">
            <div className="card-header">Available DotBots</div>
            <div className="card-body p-1">
              <div className="accordion" id="accordion-dotbots">
                {dotbots
                  .filter(dotbot => dotbot.application === ApplicationType.DotBot)
                  .map(dotbot =>
                    <DotBotItem
                      key={dotbot.address}
                      dotbot={dotbot}
                      updateActive={updateActive}
                      applyWaypoints={applyWaypoints}
                      clearWaypoints={clearWaypoints}
                      clearPositionsHistory={clearPositionsHistory}
                      updateWaypointThreshold={updateWaypointThreshold}
                      publishCommand={publishCommand}
                    />
                  )
                }
              </div>
            </div>
          </div>
        </div>
        {needDotBotMap &&
        <div className="col col-xxl-6">
          <div className="d-block d-md-none m-1">
            <DotBotsMap
              dotbots={dotbots.filter(dotbot => dotbot.application === ApplicationType.DotBot)}
              active={activeDotbot}
              updateActive={updateActive}
              showHistory={showDotBotHistory}
              updateShowHistory={updateShowHistory}
              historySize={dotbotHistorySize}
              setHistorySize={setDotbotHistorySize}
              mapClicked={mapClicked}
              mapSize={350}
              publish={publish}
            />
          </div>
          <div className="d-none d-md-block m-1">
            <DotBotsMap
              dotbots={dotbots.filter(dotbot => dotbot.application === ApplicationType.DotBot)}
              active={activeDotbot}
              updateActive={updateActive}
              showHistory={showDotBotHistory}
              updateShowHistory={updateShowHistory}
              historySize={dotbotHistorySize}
              setHistorySize={setDotbotHistorySize}
              mapClicked={mapClicked}
              mapSize={650}
              publish={publish}
            />
          </div>
        </div>
        }
      </div>
      }
      {dotbots.filter(dotbot => dotbot.application === ApplicationType.SailBot).length > 0 &&
      <div className="row">
        <div className="col col-xxl-6">
          <div className="card m-1">
            <div className="card-header">Available SailBots</div>
            <div className="card-body p-1">
              <div className="accordion" id="accordion-sailbots">
                {dotbots
                  .filter(dotbot => dotbot.application === ApplicationType.SailBot)
                  .map(dotbot =>
                    <SailBotItem
                      key={dotbot.address}
                      dotbot={dotbot}
                      updateActive={updateActive}
                      applyWaypoints={applyWaypoints}
                      clearWaypoints={clearWaypoints}
                      clearPositionsHistory={clearPositionsHistory}
                      updateWaypointThreshold={updateWaypointThreshold}
                      publishCommand={publishCommand}
                    />
                  )
                }
              </div>
            </div>
          </div>
        </div>
        <div className="col col-xxl-6">
          <div className="d-block d-md-none m-1">
            <SailBotsMap
              sailbots={dotbots.filter(dotbot => dotbot.application === ApplicationType.SailBot)}
              active={activeDotbot}
              showHistory={showSailBotHistory}
              updateShowHistory={updateShowHistory}
              mapClicked={mapClicked}
              mapSize={350}
            />
          </div>
          <div className="d-none d-md-block m-1">
            <SailBotsMap
              sailbots={dotbots.filter(dotbot => dotbot.application === ApplicationType.SailBot)}
              active={activeDotbot}
              showHistory={showSailBotHistory}
              updateShowHistory={updateShowHistory}
              mapClicked={mapClicked}
              mapSize={650}
            />
          </div>
        </div>
      </div>
      }
      {dotbots.filter(dotbot => dotbot.application === ApplicationType.XGO).length > 0 &&
      <div className="row">
        <div className="col">
          <div className="card m-1">
            <div className="card-header">Available XGO</div>
            <div className="card-body p-1">
              <div className="accordion" id="accordion-xgo">
                {dotbots
                  .filter(dotbot => dotbot.application === ApplicationType.XGO)
                  .map(dotbot =>
                    <XGOItem
                      key={dotbot.address}
                      dotbot={dotbot}
                      updateActive={updateActive}
                      publishCommand={publishCommand}
                    />
                  )
                }
              </div>
            </div>
          </div>
        </div>
      </div>
      }
      </>
      )}
      <div><button onClick={() => runOrcaStepWithState(dotbots, insertWaypoint, publishCommand, clearWaypoints)}>RUNONE</button></div>
    </div>
    </>
  );
}

function directionToRad(direction) {
  const robotDeg = (270 - direction + 360) % 360;
  return (robotDeg * Math.PI) / 180;
}

function preferredVel(dotbot) {
  // TODO: get goal from dotbot state
  let bot = {
    goal: { x: 0, y: 0 }
  }

  const dx = bot.goal.x - dotbot.lh2_position.x;
  const dy = bot.goal.y - dotbot.lh2_position.y;
  const dist = Math.sqrt(dx * dx + dy * dy);

  let preferred_vel;
  if (dist < 0.01) {
    preferred_vel = { x: 0, y: 0 };
  } else {
    const maxSpeed = 1.0;
    // Add small rotation bias to break symmetry (Right Hand Rule)
    const biasAngle = 0.2;
    const cos = Math.cos(biasAngle);
    const sin = Math.sin(biasAngle);

    const vx = (dx / dist) * maxSpeed;
    const vy = (dy / dist) * maxSpeed;

    return preferred_vel = {
      x: vx * cos - vy * sin,
      y: vx * sin + vy * cos,
    }
  }
}

async function runOrcaStepWithState (currentDotbots, insertWaypoint, publishCommand, clearWaypoints) {
  const botRadius = 0.015;

  // for (let i = 0; i < 10; i++) {
    // Process each bot that has a goal
  for (const bot of currentDotbots) {
    const agent = {
      id: bot.address,
      position: { x: bot.lh2_position.x, y: bot.lh2_position.y },
      velocity: { x: 0, y: 0 },
      radius: botRadius,
      maxSpeed: 1.0, // Must match the maxSpeed used in preferred_vel calculation
      preferredVelocity: preferredVel(bot),
    };

    // Create neighbors list (all other bots)
    const neighbors = [];
    for (const otherBot of currentDotbots) {
      if (otherBot.address === bot.address) continue; // Skip self

      neighbors.push({
        id: otherBot.address,
        position: { x: otherBot.lh2_position.x, y: otherBot.lh2_position.y },
        velocity: { x: 0, y: 0 },
        radius: botRadius,
        maxSpeed: 1.0, // Must match the maxSpeed used in preferred_vel calculation
        preferredVelocity: preferredVel(otherBot) ?? { x: 0, y: 0 },
      });
    }

    const params = { timeHorizon: 0.03 };

    // Compute ORCA velocity toward the goal
    let vNew = computeOrcaVelocityForAgent(agent, neighbors, params);
    vNew = mul(vNew, 0.1); // Scale down velocity for smoother movement

    console.log(`Bot ${bot.address} bot.lh2_position:`, bot.lh2_position);
    console.log(`Bot ${bot.address} vNew:`, vNew);

    insertWaypoint(bot.lh2_position.x + vNew.x, bot.lh2_position.y + vNew.y, bot);

    publishCommand(bot.address, bot.application, "waypoints", { threshold: bot.waypoints_threshold, waypoints: bot.waypoints });

  }

  await new Promise(r => setTimeout(r, 1000));


  for (const bot of currentDotbots) {
    clearWaypoints(bot.address, bot.application);
  }
  // }
};

export default DotBots;
