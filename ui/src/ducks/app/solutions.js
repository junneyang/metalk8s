import { call, put, takeEvery, select, delay } from 'redux-saga/effects';
import * as ApiK8s from '../../services/k8s/api';
import history from '../../history';
import { REFRESH_TIMEOUT } from '../../constants';

const APP_K8S_PART_OF_SOLUTION_LABEL = 'app.kubernetes.io/part-of';
const APP_K8S_VERSION_LABEL = 'app.kubernetes.io/version';

// Actions
export const SET_SOLUTIONS = 'SET_SOLUTIONS';
export const SET_SOLUTIONS_REFRESHING = 'SET_SOLUTIONS_REFRESHING';
export const SET_SERVICES = 'SET_SERVICES';
export const SET_ENVIRONMENTS = 'SET_ENVIRONMENTS';
const CREATE_ENVIRONMENT = 'CREATE_ENVIRONMENT';
const REFRESH_SOLUTIONS = 'REFRESH_SOLUTIONS';
const STOP_REFRESH_SOLUTIONS = 'STOP_REFRESH_SOLUTIONS';
const REFRESH_ENVIRONMENTS = 'REFRESH_ENVIRONMENTS';
const STOP_REFRESH_ENVIRONMENTS = 'STOP_REFRESH_ENVIRONMENTS';
export const SET_ENVIRONMENTS_REFRESHING = 'SET_ENVIRONMENTS_REFRESHING';

// Reducer
const defaultState = {
  solutions: [],
  services: [],
  environments: [],
  isSolutionsRefreshing: false,
  isEnvironmentsRefreshing: false,
};

export default function reducer(state = defaultState, action = {}) {
  switch (action.type) {
    case SET_SOLUTIONS:
      return { ...state, solutions: action.payload };
    case SET_SERVICES:
      return { ...state, services: action.payload };
    case SET_ENVIRONMENTS:
      return { ...state, environments: action.payload };
    case SET_SOLUTIONS_REFRESHING:
      return { ...state, isSolutionsRefreshing: action.payload };
    case SET_ENVIRONMENTS_REFRESHING:
      return { ...state, isEnvironmentsRefreshing: action.payload };
    default:
      return state;
  }
}

// Actions Creator

export function setSolutionsAction(solutions) {
  return { type: SET_SOLUTIONS, payload: solutions };
}

export function setSolutionsRefeshingAction(payload) {
  return { type: SET_SOLUTIONS_REFRESHING, payload };
}

export function setServicesAction(services) {
  return { type: SET_SERVICES, payload: services };
}

export const setEnvironmentsAction = environments => {
  return { type: SET_ENVIRONMENTS, payload: environments };
};

export const refreshSolutionsAction = () => {
  return { type: REFRESH_SOLUTIONS };
};

export function setEnvironmentsRefeshingAction(payload) {
  return { type: SET_ENVIRONMENTS_REFRESHING, payload };
}

export const stopRefreshSolutionsAction = () => {
  return { type: STOP_REFRESH_SOLUTIONS };
};

export const refreshEnvironmentsAction = () => {
  return { type: REFRESH_ENVIRONMENTS };
};

export const stopRefreshEnvironmentsAction = () => {
  return { type: STOP_REFRESH_ENVIRONMENTS };
};

export function createEnvironmentAction(newEnvironment) {
  return { type: CREATE_ENVIRONMENT, payload: newEnvironment };
}

export function* createEnvironment(action) {
  const newEnvironment = action.payload;

  const body = {
    apiVersion: 'solutions.metalk8s.scality.com/v1alpha1',
    kind: 'Environment',
    metadata: {
      name: newEnvironment.name,
    },
    spec: {
      description: newEnvironment.description,
      solutions: [],
    },
  };

  const result = yield call(ApiK8s.createEnvironment, body);
  if (!result.error) {
    yield call(fetchEnvironments);
    history.push('/solutions');
  }
  return result;
}

export function* fetchUIServices() {
  const result = yield call(ApiK8s.getUIServiceForAllNamespaces);
  if (!result.error) {
    yield put(setServicesAction(result.body.items));
  }
  return result;
}

export function* fetchSolutions() {
  const result = yield call(ApiK8s.getSolutionsConfigMapForAllNamespaces);
  if (!result.error) {
    const solutionsConfigMap = result.body.items[0];
    if (solutionsConfigMap && solutionsConfigMap.data) {
      const solutions = Object.keys(solutionsConfigMap.data).map(key => {
        return {
          name: key,
          versions: JSON.parse(solutionsConfigMap.data[key]),
        };
      });
      const services = yield select(state => state.app.solutions.services);
      solutions.forEach(sol => {
        sol.versions.forEach(version => {
          if (version.deployed) {
            const sol_service = services.find(
              service =>
                service.metadata.labels &&
                service.metadata.labels[APP_K8S_PART_OF_SOLUTION_LABEL] ===
                  sol.name &&
                service.metadata.labels[APP_K8S_VERSION_LABEL] ===
                  version.version,
            );
            version.ui_url = sol_service
              ? `http://localhost:${sol_service.spec.ports[0].nodePort}` // TO BE IMPROVED: we can not get the Solution UI's IP so far
              : '';
          }
        });
      });
      yield put(setSolutionsAction(solutions));
    }
  }
  return result;
}

export function* fetchEnvironments() {
  const result = yield call(ApiK8s.getEnvironments);
  if (!result.error) {
    yield put(setEnvironmentsAction(result?.body?.items ?? []));
  }
  return result;
}

export function* refreshSolutions() {
  yield put(setSolutionsRefeshingAction(true));

  const resultFetchUIServices = yield call(fetchUIServices);
  const resultFetchSolutions = yield call(fetchSolutions);

  if (!resultFetchSolutions.error && !resultFetchUIServices.error) {
    yield delay(REFRESH_TIMEOUT);
    const isRefreshing = yield select(
      state => state.app.solutions.isSolutionsRefreshing,
    );
    if (isRefreshing) {
      yield call(refreshSolutions);
    }
  }
}

export function* stopRefreshSolutions() {
  yield put(setSolutionsRefeshingAction(false));
}

export function* refreshEnvironments() {
  yield put(setEnvironmentsRefeshingAction(true));

  const resultFetchEnvironments = yield call(fetchEnvironments);

  if (!resultFetchEnvironments.error) {
    yield delay(REFRESH_TIMEOUT);
    const isRefreshing = yield select(
      state => state.app.solutions.isEnvironmentsRefreshing,
    );
    if (isRefreshing) {
      yield call(refreshEnvironments);
    }
  }
}

export function* stopRefreshEnvironments() {
  yield put(setEnvironmentsRefeshingAction(false));
}

// Sagas
export function* solutionsSaga() {
  yield takeEvery(REFRESH_SOLUTIONS, refreshSolutions);
  yield takeEvery(STOP_REFRESH_SOLUTIONS, stopRefreshSolutions);
  yield takeEvery(REFRESH_ENVIRONMENTS, refreshEnvironments);
  yield takeEvery(STOP_REFRESH_ENVIRONMENTS, stopRefreshEnvironments);
  yield takeEvery(CREATE_ENVIRONMENT, createEnvironment);
}
